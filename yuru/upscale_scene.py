#!/usr/bin/env python3
"""Upscale an original RGB scene with pinned classical SwinIR DF2K x2.

Requires PyTorch, timm, OpenCV, NumPy and requests in the invoking environment.
The official non-GAN model and its inference code are downloaded to the user
cache and SHA256-verified before import. No denoising, face enhancement,
segmentation, generated cutout, palette remapping or post-sharpening is used.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import urllib.request

COMMIT = '6545850fbf8df298df73d81f3e8cba638787c8bd'
MODEL = '001_classicalSR_DF2K_s64w8_SwinIR-M_x2.pth'
MODEL_URL = 'https://github.com/JingyunLiang/SwinIR/releases/download/v0.0/' + MODEL
MODEL_SHA256 = '2032ebf8f401dd3ce2fae5f3852117cb72101ec6ed8358faa64c2a3fa09ed4ac'
CODE = {
    'main_test_swinir.py': '812671208d948a7a36241aeb2cd7371dfb19cac9cd976c7bc296fd786ebfca2e',
    'models/network_swinir.py': '9e143898679ebeebc5d2fc94ad1b89c38aa4a4d43da4e0fcba0f93e476994913',
    'utils/util_calculate_psnr_ssim.py': 'b4242d9e8428667418d964a481422eea45736da25d754569dc7316ae82420140',
}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def cached(path, url, expected):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with urllib.request.urlopen(url, timeout=60) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != expected:
            raise RuntimeError('Download checksum mismatch: ' + url)
        fd, staged = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(data)
            os.replace(staged, path)
        finally:
            if os.path.exists(staged):
                os.unlink(staged)
    if sha256(path) != expected:
        raise RuntimeError('Cached file checksum mismatch; preserving file: ' + str(path))


def upscale(args):
    import cv2
    import numpy as np
    import timm
    import torch
    for name, expected in CODE.items():
        cached(args.cache / name,
               f'https://raw.githubusercontent.com/JingyunLiang/SwinIR/{COMMIT}/{name}', expected)
    model_path = args.cache / MODEL
    cached(model_path, MODEL_URL, MODEL_SHA256)
    sys.path.insert(0, str(args.cache))
    from main_test_swinir import define_model, test
    torch.set_num_threads(4)
    device = torch.device(args.device)
    settings = SimpleNamespace(task='classical_sr', scale=2, training_patch_size=64,
                               model_path=str(model_path), tile=args.tile, tile_overlap=32)
    # The classical task uses the official pixelshuffle model, not the real_sr GAN model.
    model = define_model(settings).float().eval().to(device)
    original = cv2.imread(str(args.source), cv2.IMREAD_UNCHANGED)
    if original is None or original.ndim != 3 or original.shape[2] != 3 or original.dtype != np.uint8:
        raise ValueError('Source must be an 8-bit RGB scene; alpha cutouts are not accepted')
    image = original[:, :, ::-1].copy().astype(np.float32) / 255
    image = torch.from_numpy(np.transpose(image, (2, 0, 1))).unsqueeze(0).float().to(device)
    h, w = original.shape[:2]
    with torch.inference_mode():
        # Match the official inference path: mirrored window padding, overlap-averaged tiles.
        hp, wp = (h // 8 + 1) * 8 - h, (w // 8 + 1) * 8 - w
        image = torch.cat([image, torch.flip(image, [2])], 2)[:, :, :h + hp, :]
        image = torch.cat([image, torch.flip(image, [3])], 3)[:, :, :, :w + wp]
        output = test(image, model, settings, 8)[..., :h * 2, :w * 2]
    output = output.squeeze().float().cpu().clamp(0, 1).numpy()
    output = (np.transpose(output[::-1, :, :], (1, 2, 0)) * 255).round().astype(np.uint8)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fd, staged = tempfile.mkstemp(prefix='.' + args.output.name, suffix='.png', dir=args.output.parent)
    os.close(fd)
    try:
        if not cv2.imwrite(staged, output):
            raise RuntimeError('Could not encode output PNG')
        os.chmod(staged, 0o644)
        os.replace(staged, args.output)
    finally:
        if os.path.exists(staged):
            os.unlink(staged)
    metadata = {'source': {'path': str(args.source), 'sha256': sha256(args.source), 'dimensions': [w, h]},
                'output': {'path': str(args.output), 'sha256': sha256(args.output), 'dimensions': [w * 2, h * 2]},
                'model': {'name': MODEL, 'url': MODEL_URL, 'sha256': MODEL_SHA256,
                          'task': 'classical_sr', 'scale': 2, 'training_patch_size': 64, 'GAN': False},
                'code': {'repository': 'https://github.com/JingyunLiang/SwinIR', 'commit': COMMIT, 'sha256': CODE},
                'inference': {'device': str(device), 'dtype': 'float32', 'tile': args.tile, 'tile_overlap': 32,
                              'torch': torch.__version__, 'timm': timm.__version__, 'opencv': cv2.__version__},
                'limits': 'No high-resolution ground truth is available. This reconstructs an enlargement; it does not establish recovery of missing original detail.'}
    if args.metadata:
        args.metadata.write_text(json.dumps(metadata, indent=2) + '\n')
    print(json.dumps(metadata['output']))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cache', type=Path, default=Path.home() / '.cache/yuru-swinir' / COMMIT)
    parser.add_argument('--device', choices=['cuda', 'cpu'], default='cuda')
    parser.add_argument('--tile', type=int, default=192)
    parser.add_argument('--metadata', type=Path)
    args = parser.parse_args()
    if args.source.resolve() == args.output.resolve():
        parser.error('Source and output must be different files')
    if args.tile <= 32 or args.tile % 8:
        parser.error('--tile must be a multiple of 8 greater than 32')
    upscale(args)
