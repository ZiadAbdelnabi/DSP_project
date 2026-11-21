import os
import numpy as np
import cv2

def load_color_and_gray(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Image doesn't exist: {path}")

    if cv2 is not None:
        img_color = cv2.imread(path, cv2.IMREAD_COLOR)
        if img_color is None:
            raise ValueError(f"OpenCV can't read the image: {path}")

        img_gray = cv2.cvtColor(img_color, cv2.COLOR_BGR2GRAY)

        img_color_rgb = cv2.cvtColor(img_color, cv2.COLOR_BGR2RGB)

        return img_color_rgb, img_gray.astype(float)
    else:
        raise ImportError("OpenCV is required for loading color images.")


def to_uint8(arr, normalize=False):
    a = np.asarray(arr, dtype=float)
    if normalize:
        lo, hi = a.min(), a.max()
        a = (a - lo) / (hi - lo) * 255 if hi > lo else np.zeros_like(a)
    return np.clip(a, 0, 255).astype(np.uint8)

def save_image(arr, path, normalize=False):
    out = to_uint8(arr, normalize)
    if cv2 is not None:
        cv2.imwrite(path, out)
    else:
        from PIL import Image
        Image.fromarray(out).save(path)

def mse(a, b):
    return float(np.mean((a - b) ** 2))
def psnr(a, b, peak=255.0):
    m = mse(a, b)
    return float("inf") if m == 0 else float(10 * np.log10(peak ** 2 / m))


def fourier_spectrum(img):
    Fs = np.fft.fftshift(np.fft.fft2(img))
    return Fs, np.log(1 + np.abs(Fs))


def inverse_fourier(Fs):
    return np.real(np.fft.ifft2(np.fft.ifftshift(Fs)))


"Part A: 2D Fourier & Filtering"
def circular_mask(shape, D0):
    M, N = shape
    v, u = np.ogrid[:M, :N]
    D = np.sqrt((u - N // 2) ** 2 + (v - M // 2) ** 2)
    return (D <= D0).astype(float)

def run_filtering(img, D0=30):
    Fs, log_mag = fourier_spectrum(img)
    lp_mask = circular_mask(img.shape, D0)
    hp_mask = 1 - lp_mask
    return {
        "original": img,
        "spectrum": log_mag,
        "lowpass_mask": lp_mask,
        "lowpass_image": inverse_fourier(Fs * lp_mask),
        "highpass_mask": hp_mask,
        "highpass_image": inverse_fourier(Fs * hp_mask),
    }


"Part B: Denoising and Evaluation"
def add_periodic_noise(img, A, u0, v0):
    M, N = img.shape
    y, x = np.ogrid[:M, :N]
    return img + A * np.sin(2 * np.pi * (u0 * x / N + v0 * y / M))


def notch_mask(shape, u0, v0, radius):
    M, N = shape
    cx, cy = N // 2, M // 2
    y, x = np.ogrid[:M, :N]
    mask = np.ones(shape)
    for px, py in [(cx + u0, cy + v0), (cx - u0, cy - v0)]:
        mask[np.sqrt((x - px) ** 2 + (y - py) ** 2) <= radius] = 0
    return mask


def find_noise_peak(Fs):
    M, N = Fs.shape
    mag = np.abs(Fs).copy()
    mag[M // 2, N // 2] = 0
    py, px = np.unravel_index(np.argmax(mag), mag.shape)
    return int(px - N // 2), int(py - M // 2)

def run_denoising(img, A=40, u0=30, v0=20, radius=3):
    M, N = img.shape
    if not (abs(u0) < N // 2 and abs(v0) < M // 2):
        raise ValueError("u0 and v0 must be smaller than half the width/height of the image.")
    if u0 == 0 and v0 == 0:
        raise ValueError("u0 and v0 cannot both be zero.")

    noisy = add_periodic_noise(img, A, u0, v0)
    Fn, noisy_spectrum = fourier_spectrum(noisy)
    mask = notch_mask(img.shape, u0, v0, radius)
    restored = np.clip(inverse_fourier(Fn * mask), 0, 255)

    return {
        "original": img,
        "noisy": noisy,
        "noisy_spectrum": noisy_spectrum,
        "notch_mask": mask,
        "filtered_spectrum": np.log(1 + np.abs(Fn * mask)),
        "restored": restored,
        "detected_peak": find_noise_peak(Fn),
        "mse_noisy": mse(img, noisy),
        "psnr_noisy": psnr(img, noisy),
        "mse_restored": mse(img, restored),
        "psnr_restored": psnr(img, restored),
    }


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "photos/im2.jpg"
    img_color, img_gray = load_color_and_gray(path)
    print("shape:", img_gray.shape)

    f = run_filtering(img_gray, D0=30)
    print("filtering keys:", list(f))

    d = run_denoising(img_gray, A=40, u0=30, v0=20, radius=3)
    print("detected peak:", d["detected_peak"])
    print(f"Noisy   : MSE={d['mse_noisy']:.3f}  PSNR={d['psnr_noisy']:.2f} dB")
    print(f"Restored: MSE={d['mse_restored']:.3f}  PSNR={d['psnr_restored']:.2f} dB")