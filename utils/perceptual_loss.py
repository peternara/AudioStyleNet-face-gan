import os
import torch
import torch.nn as nn

from torchvision.models.vgg import vgg16, vgg19


VGG_MEAN = [0.485, 0.456, 0.406]
VGG_STD = [0.229, 0.224, 0.225]
ZHANG_WEIGHTING_FMAPS = [64, 128, 256, 512, 512]


class VGG19Loss(nn.Module):
    """
    Source: https://github.com/NVlabs/SPADE/blob/master/models/networks/loss.py
    Perceptual loss that uses a pretrained VGG network
    """

    def __init__(self, device):
        super(VGG19Loss, self).__init__()
        self.vgg = VGG19().to(device)
        self.criterion = nn.L1Loss()
        self.weights = [1.0 / 32, 1.0 / 16, 1.0 / 8, 1.0 / 4, 1.0]

    def forward(self, x, y):
        loss = 0.
        x_vgg, y_vgg = self.vgg(x), self.vgg(y)
        for i in range(len(x_vgg)):
            loss += self.weights[i] * \
                self.criterion(x_vgg[i], y_vgg[i].detach())
        return loss


class VGG19(nn.Module):
    def __init__(self, requires_grad=False):
        super().__init__()
        vgg_pretrained_features = vgg19(pretrained=True).features
        self.slice1 = nn.Sequential()
        self.slice2 = nn.Sequential()
        self.slice3 = nn.Sequential()
        self.slice4 = nn.Sequential()
        self.slice5 = nn.Sequential()
        for x in range(2):
            self.slice1.add_module(str(x), vgg_pretrained_features[x])
        for x in range(2, 7):
            self.slice2.add_module(str(x), vgg_pretrained_features[x])
        for x in range(7, 12):
            self.slice3.add_module(str(x), vgg_pretrained_features[x])
        for x in range(12, 21):
            self.slice4.add_module(str(x), vgg_pretrained_features[x])
        for x in range(21, 30):
            self.slice5.add_module(str(x), vgg_pretrained_features[x])
        if not requires_grad:
            for param in self.parameters():
                param.requires_grad = False

    def forward(self, x):
        h_relu1 = self.slice1(x)
        h_relu2 = self.slice2(h_relu1)
        h_relu3 = self.slice3(h_relu2)
        h_relu4 = self.slice4(h_relu3)
        h_relu5 = self.slice5(h_relu4)
        out = [h_relu1, h_relu2, h_relu3, h_relu4, h_relu5]
        return out


class VGG16(nn.Module):
    def __init__(self, requires_grad=False):
        super(VGG16, self).__init__()
        vgg_pretrained_features = vgg16(pretrained=True).features
        self.slice1 = nn.Sequential()
        self.slice2 = nn.Sequential()
        self.slice3 = nn.Sequential()
        self.slice4 = nn.Sequential()
        self.slice5 = nn.Sequential()
        for x in range(4):
            self.slice1.add_module(str(x), vgg_pretrained_features[x])
        for x in range(4, 9):
            self.slice2.add_module(str(x), vgg_pretrained_features[x])
        for x in range(9, 16):
            self.slice3.add_module(str(x), vgg_pretrained_features[x])
        for x in range(16, 23):
            self.slice4.add_module(str(x), vgg_pretrained_features[x])
        for x in range(23, 30):
            self.slice5.add_module(str(x), vgg_pretrained_features[x])

        self.mean = nn.Parameter(torch.tensor(VGG_MEAN).view(1, -1, 1, 1))
        self.std = nn.Parameter(torch.tensor(VGG_STD).view(1, -1, 1, 1))

        for param in self.parameters():
            param.requires_grad = False

    def forward(self, x):
        # Normalize
        x = (x - self.mean) / self.std

        # Get preceptual losses
        h_relu1 = self.slice1(x)
        h_relu2 = self.slice2(h_relu1)
        h_relu3 = self.slice3(h_relu2)
        h_relu4 = self.slice4(h_relu3)
        h_relu5 = self.slice5(h_relu4)
        out = [h_relu1, h_relu2, h_relu3, h_relu4, h_relu5]
        return out


class VGG16Loss(nn.Module):
    """
    LPIPS metric using VGG-16 and Zhang weighting. (https://arxiv.org/abs/1801.03924)

    Takes reference images and corrupted images as an input and outputs the perceptual
    distance between the image pairs.
    """
    def __init__(self, device):
        super(VGG16Loss, self).__init__()
        self.vgg = VGG16().to(device)
        self.criterion = nn.MSELoss()

        w = torch.load(
            os.path.dirname(os.path.abspath(__file__)) + '/perceptual_weights/vgg.pth')
        self.zhang_w = [w[key].to(device) for key in w.keys()]

    def forward(self, x, y):
        x_vgg, y_vgg = self.vgg(x), self.vgg(y)

        x_vgg_normalized = []
        for f in x_vgg:
            n = torch.sum(f ** 2, dim=1, keepdim=True) ** 0.5
            x_vgg_normalized.append(f / (n + 1e-10))

        y_vgg_normalized = []
        for f in y_vgg:
            n = torch.sum(f ** 2, dim=1, keepdim=True) ** 0.5
            y_vgg_normalized.append(f / (n + 1e-10))

        diff = [(x_ - y_) ** 2 for x_, y_ in zip(x_vgg_normalized, y_vgg_normalized)]
        reduced = [diff[i] * self.zhang_w[i] for i in range(len(diff))]

        result = sum(red.mean() for red in reduced)

        return result