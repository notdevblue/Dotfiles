#!/usr/bin/env python3
"""Reproduce RGB scene enlargement with pinned models and optional restoration blending.

Default SwinIR classical x2 retains its original official inference path.
Researched HAT, Real-ESRGAN anime and Lexica models use Spandrel float32 inference.
All outputs share exact 2x coordinates with the independently traced alpha masks.
Requires PyTorch, timm, OpenCV, NumPy; candidate models additionally need Spandrel.
No face enhancement, alpha inference, extra sharpening or palette remapping.
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



CANDIDATES = {
    'hat': {
        'name': 'HAT_SRx2.pth', 'scale': 2, 'architecture': 'HAT',
        'url': 'https://drive.usercontent.google.com/download?id=1M2HZD6i9ZNpsJR-dKKBjlzL_AXntCvGR&export=download&confirm=t',
        'sha256': '35e9409849016ab2bfc0c549639ea4f1d4d5b2bdd75f856a925e124dd05670d0',
        'source': 'https://github.com/XPixelGroup/HAT',
        'purpose': 'Classical DF2K x2, L1 pixel loss; not Real_HAT_GAN',
    },
    'anime': {
        'name': 'RealESRGAN_x4plus_anime_6B.pth', 'scale': 4, 'architecture': 'ESRGAN',
        'url': 'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth',
        'sha256': 'f872d837d3c90ed2e05227bed711af5671a6fd1c9f7d7e91c911a61f155e99da',
        'source': 'https://github.com/xinntao/Real-ESRGAN',
        'purpose': 'Official static anime/illustration x4, 6 RRDB blocks',
    },
    'lexica': {
        'name': '2xLexicaSwinIR.pth', 'scale': 2, 'architecture': 'SwinIR',
        'url': 'https://raw.githubusercontent.com/Phhofm/models/43a9792f0b7fda901216fbcceb925af9885eafbd/2xLexicaSwinIR/2xLexicaSwinIR.pth',
        'sha256': '443441716478b970eba85d21e2d3e4abf8273b82b1030cb91b8885fe0c98f575',
        'source': 'https://github.com/Phhofm/models/tree/43a9792f0b7fda901216fbcceb925af9885eafbd/2xLexicaSwinIR',
        'purpose': 'AI-generated image x2; not L1-only classical restoration',
    },
}


def upscale_candidate(args):
    """Run researched RGB checkpoints; all outputs use the existing exact 2x coordinates."""
    import importlib.metadata
    import time
    import cv2
    import numpy as np
    import spandrel
    import torch
    spec=CANDIDATES[args.model]
    checkpoint=args.candidate_cache/spec['name']
    cached(checkpoint,spec['url'],spec['sha256'])
    torch.set_num_threads(4)
    torch.backends.cuda.matmul.allow_tf32=False
    torch.backends.cudnn.allow_tf32=False
    # Safe state dictionaries only; never unpickle arbitrary checkpoint objects.
    state=torch.load(checkpoint,map_location='cpu',weights_only=True)
    descriptor=spandrel.ModelLoader().load_from_state_dict(state)
    if (descriptor.architecture.id!=spec['architecture'] or descriptor.scale!=spec['scale']
            or descriptor.input_channels!=3 or descriptor.output_channels!=3):
        raise ValueError('Checkpoint architecture, scale or RGB channels differ from the pinned model')
    model=descriptor.eval().float().to(args.device)
    original=cv2.imread(str(args.source),cv2.IMREAD_UNCHANGED)
    if original is None or original.ndim!=3 or original.shape[2]!=3 or original.dtype!=np.uint8:
        raise ValueError('Source must be an 8-bit RGB scene; alpha is handled separately')
    h,w=original.shape[:2];scale=descriptor.scale
    rgb=original[:,:,::-1].copy().astype(np.float32)/255
    image=torch.from_numpy(rgb.transpose(2,0,1)).unsqueeze(0)
    output=np.empty((h*scale,w*scale,3),dtype=np.float32)
    start=time.monotonic();pad=args.tile_pad
    with torch.inference_mode():
        for y in range(0,h,args.tile):
            for x in range(0,w,args.tile):
                x1,y1=max(0,x-pad),max(0,y-pad)
                x2,y2=min(w,x+args.tile+pad),min(h,y+args.tile+pad)
                tile=image[:,:,y1:y2,x1:x2].to(args.device)
                result=model(tile).squeeze(0).float().cpu().numpy().transpose(1,2,0)
                tw,th=min(args.tile,w-x),min(args.tile,h-y)
                output[y*scale:(y+th)*scale,x*scale:(x+tw)*scale]=result[(y-y1)*scale:(y-y1+th)*scale,(x-x1)*scale:(x-x1+tw)*scale]
            print(json.dumps({'model':args.model,'source':args.source.name,'completed_rows':min(h,y+args.tile),'rows':h}),flush=True)
    output=np.clip(output,0,1)
    if scale!=2:
        # Float RGB area reduction before the only 8-bit quantization; exact shared alpha geometry.
        output=cv2.resize(output,(w*2,h*2),interpolation=cv2.INTER_AREA)
    encoded=np.rint(output[:,:,::-1]*255).astype(np.uint8)
    blend=None
    if args.preserve_base:
        base=cv2.imread(str(args.preserve_base),cv2.IMREAD_UNCHANGED)
        if base is None or base.shape!=encoded.shape or base.dtype!=np.uint8:
            raise ValueError('Preservation base must be an RGB8 PNG at exact 2x source dimensions')
        encoded=(base.astype(np.float32)*(1-args.restoration_strength)
                 +encoded.astype(np.float32)*args.restoration_strength).astype(np.uint8)
        blend={'preservation_base':str(args.preserve_base),'base_sha256':sha256(args.preserve_base),
               'restoration_strength':args.restoration_strength,'color_space':'encoded RGB8',
               'method':'(1-strength)*base + strength*restored, truncate once to uint8'}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    fd,staged=tempfile.mkstemp(prefix='.'+args.output.name,suffix='.png',dir=args.output.parent);os.close(fd)
    try:
        if not cv2.imwrite(staged,encoded):raise RuntimeError('Could not encode RGB PNG')
        os.chmod(staged,0o644);os.replace(staged,args.output)
    finally:
        if os.path.exists(staged):os.unlink(staged)
    metadata={'source':{'path':str(args.source),'sha256':sha256(args.source),'dimensions':[w,h]},
              'output':{'path':str(args.output),'sha256':sha256(args.output),'dimensions':[w*2,h*2]},
              'model':dict(spec,key=args.model),
              'inference':{'device':args.device,'dtype':'float32','tile':args.tile,'tile_pad':pad,
                           'native_scale':scale,'stored_scale':2,'native_to_stored':'INTER_AREA in float RGB' if scale!=2 else 'none',
                           'face_enhancement':False,'extra_denoise':False,'extra_sharpen':False,'recolor':False,
                           'torch':torch.__version__,'spandrel':importlib.metadata.version('spandrel'),
                           'opencv':cv2.__version__,'seconds':round(time.monotonic()-start,3)},
              'code':{'runner_sha256':sha256(__file__)},'blend':blend,
              'limits':'Perceived-detail comparison, not recovery of unavailable ground-truth high-resolution art.'}
    if args.metadata:
        args.metadata.parent.mkdir(parents=True,exist_ok=True)
        args.metadata.write_text(json.dumps(metadata,indent=2)+'\n')
    print(json.dumps(metadata['output']),flush=True)


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
    parser.add_argument('--model', choices=['swinir', *CANDIDATES], default='swinir')
    parser.add_argument('--candidate-cache', type=Path, default=Path.home()/'.cache/yuru-upscale-candidates')
    parser.add_argument('--tile-pad', type=int, default=32)
    parser.add_argument('--preserve-base', type=Path, help='Optional same-source RGB2x preservation base')
    parser.add_argument('--restoration-strength', type=float, default=1.0)
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
    if args.tile_pad<16 or args.tile_pad%8:
        parser.error('--tile-pad must be a multiple of 8 at least 16')
    if not 0<args.restoration_strength<=1:
        parser.error('--restoration-strength must be in (0, 1]')
    if args.preserve_base and (args.model=='swinir' or args.preserve_base.resolve()==args.output.resolve()):
        parser.error('--preserve-base requires a candidate model and a separate output file')
    if not args.preserve_base and args.restoration_strength!=1:
        parser.error('--restoration-strength requires --preserve-base')
    if args.model=='swinir':
        upscale(args)
    else:
        upscale_candidate(args)
