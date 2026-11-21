import os
import queue
import threading
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk

import image_signal_core as core

THUMB = 280
class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        self.title("DSP Project - Modern UI")
        self.geometry("1200x750")

        self.img = None
        self.img_color = None
        self.results = {}
        self.photos = []
        self.q = queue.Queue()

        self._build_controls()
        self._build_tabs()
        self.after(100, self._poll)

    def _build_controls(self):
        left = ctk.CTkFrame(self, corner_radius=10)
        left.pack(side="left", fill="y", padx=10, pady=10)

        ctk.CTkButton(left, text="Browse image...", command=self.browse).pack(fill="x", padx=10, pady=5)
        self.lbl_img = ctk.CTkLabel(left, text="No image loaded", wraplength=230)
        self.lbl_img.pack(fill="x", padx=10, pady=(4, 10))

        fa = ctk.CTkFrame(left, corner_radius=10)
        fa.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(fa, text="Part A - Filtering", font=("Arial", 14, "bold")).pack(anchor="w", padx=10, pady=5)

        ctk.CTkLabel(fa, text="D0 (cutoff radius)").pack(anchor="w", padx=10)
        self.d0 = ctk.IntVar(value=30)
        self.sc_d0 = ctk.CTkSlider(fa, from_=1, to=200, number_of_steps=199, variable=self.d0)
        self.sc_d0.pack(fill="x", padx=10)

        ctk.CTkButton(fa, text="Run Part A", command=self.run_a).pack(fill="x", padx=10, pady=10)

        fb = ctk.CTkFrame(left, corner_radius=10)
        fb.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(fb, text="Part B - Denoising", font=("Arial", 14, "bold")).pack(anchor="w", padx=10, pady=5)

        self.vars = {}
        params_config = [
            ("A (noise amplitude)", 40, 1, 255),
            ("u0 (cycles on width)", 30, -2000, 2000),
            ("v0 (cycles on height)", 20, -2000, 2000),
            ("Notch radius", 3, 1, 50)
        ]

        for name, default, lo, hi in params_config:
            row = ctk.CTkFrame(fb)
            row.pack(fill="x", padx=10, pady=2)

            ctk.CTkLabel(row, text=name, width=150, anchor="w").pack(side="left")

            v = tk.IntVar(value=default)
            self.vars[name.split()[0]] = v

            spin = tk.Spinbox(
                row,
                from_=lo,
                to=hi,
                textvariable=v,
                width=7,
                bg="#3d3d3d",
                fg="white",
                buttonbackground="#2b2b2b",
                activebackground="#505050",
                highlightthickness=0
            )
            spin.pack(side="right", padx=5)

        ctk.CTkButton(fb, text="Run Part B", command=self.run_b).pack(fill="x", padx=10, pady=10)

        self.lbl_metrics = ctk.CTkLabel(fb, text="", justify="left", wraplength=230, text_color="#00ff00")
        self.lbl_metrics.pack(fill="x", padx=10, pady=5)

        ctk.CTkButton(left, text="Save results...", command=self.save_results).pack(fill="x", padx=10, pady=10)
        self.status = ctk.CTkLabel(left, text="Ready", text_color="gray")
        self.status.pack(fill="x", padx=10, pady=5)

    def _build_tabs(self):
        nb = ctk.CTkTabview(self)
        nb.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        tab_a = nb.add("Part A - Fourier & Filtering")
        tab_b = nb.add("Part B - Denoising")

        self.panels = {"A": [], "B": []}

        for key, tab in [("A", tab_a), ("B", tab_b)]:
            for i in range(7):
                cell = ctk.CTkFrame(tab, corner_radius=5)
                cell.grid(row=i // 3, column=i % 3, sticky="nsew", padx=5, pady=5)

                img_lbl = ctk.CTkLabel(cell, text="")
                img_lbl.pack(pady=5)

                cap = ctk.CTkLabel(cell, text="", font=("Arial", 10))
                cap.pack(pady=2)

                self.panels[key].append((img_lbl, cap))

            for c in range(3):
                tab.columnconfigure(c, weight=1)

    def browse(self):
        path = filedialog.askopenfilename(
            filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp"), ("All", "*.*")])
        if not path:
            return
        try:
            self.img_color, self.img_gray = core.load_color_and_gray(path)

            self.img = self.img_gray

        except Exception as e:
            messagebox.showerror("Error", str(e))
            return

        M, N = self.img.shape
        self.lbl_img.configure(text=f"{os.path.basename(path)}\nsize: {N} x {M}")
        self.status.configure(text="Image loaded")

    def _need_image(self):
        if self.img is None:
            messagebox.showwarning("No image", "Load an image first.")
            return False
        return True

    def _run_async(self, key, fn):
        self.status.configure(text="Processing...")
        def worker():
            try:
                self.q.put((key, "ok", fn()))
            except Exception as e:
                self.q.put((key, "err", e))
        threading.Thread(target=worker, daemon=True).start()

    def run_a(self):
        if self._need_image():
            d0 = int(self.d0.get())
            self._run_async("A", lambda: core.run_filtering(self.img, d0))

    def run_b(self):
        if not self._need_image():
            return
        try:
            A = int(self.vars["A"].get())
            u0 = int(self.vars["u0"].get())
            v0 = int(self.vars["v0"].get())
            r = int(self.vars["Notch"].get())
        except:
            messagebox.showerror("Error", "Parameters must be integers.")
            return
        self._run_async("B", lambda: core.run_denoising(self.img, A, u0, v0, r))

    def _poll(self):
        try:
            while True:
                key, status, payload = self.q.get_nowait()
                if status == "err":
                    self.status.configure(text="Error")
                    messagebox.showerror("Error", str(payload))
                else:
                    self.results[key] = payload
                    (self._show_a if key == "A" else self._show_b)(payload)
                    self.status.configure(text="Done")
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _put(self, key, idx, arr, caption, normalize=False):
        im = Image.fromarray(core.to_uint8(arr, normalize))
        im.thumbnail((THUMB, THUMB))
        photo = ImageTk.PhotoImage(im)
        self.photos.append(photo)
        lbl, cap = self.panels[key][idx]
        lbl.configure(image=photo)
        cap.configure(text=caption)

    def _show_a(self, r):
        self.photos.clear()
        original_display = self.img_color if self.img_color is not None else r["original"]
        self._put("A", 0, original_display, "Original (Color)")

        gray_display = self.img_gray if self.img_gray is not None else r["original"]
        self._put("A", 1, gray_display, "Grayscale Input")

        self._put("A", 2, r["spectrum"], "Magnitude spectrum", True)
        self._put("A", 3, r["lowpass_mask"], "Low-Pass mask", True)
        self._put("A", 4, r["lowpass_image"], "Low-Pass result")
        self._put("A", 5, r["highpass_mask"], "High-Pass mask", True)
        self._put("A", 6, r["highpass_image"], "High-Pass result", True)

    def _show_b(self, r):
        original_display = self.img_color if self.img_color is not None else r["original"]
        self._put("B", 0, original_display, "Original (Color)")

        gray_display = self.img_gray if self.img_gray is not None else r["original"]
        self._put("B", 1, gray_display, "Grayscale Input")

        self._put("B", 2, r["noisy"], f"Noisy ({r['psnr_noisy']:.2f} dB)")
        self._put("B", 3, r["noisy_spectrum"], "Noisy spectrum", True)
        self._put("B", 4, r["notch_mask"], "Notch mask", True)
        self._put("B", 5, r["filtered_spectrum"], "Filtered spectrum", True)
        self._put("B", 6, r["restored"], f"Restored ({r['psnr_restored']:.2f} dB)")

        pu, pv = r["detected_peak"]
        self.lbl_metrics.configure(text=(
            f"Detected peak: ({pu}, {pv})\n"
            f"Noisy:    MSE {r['mse_noisy']:.3f} | PSNR {r['psnr_noisy']:.2f} dB\n"
            f"Restored: MSE {r['mse_restored']:.3f} | PSNR {r['psnr_restored']:.2f} dB"))

    def save_results(self):
        if not self.results:
            messagebox.showinfo("Nothing to save", "Run Part A or Part B first.")
            return
        folder = filedialog.askdirectory(title="Choose output folder")
        if not folder:
            return
        norm = {"spectrum", "lowpass_mask", "highpass_mask", "highpass_image",
                "noisy_spectrum", "notch_mask", "filtered_spectrum"}
        for part, res in self.results.items():
            for name, val in res.items():
                if hasattr(val, "ndim") and val.ndim == 2:
                    core.save_image(val, os.path.join(folder, f"part{part}_{name}.png"),
                                    normalize=name in norm)
        self.status.configure(text="Saved")

if __name__ == "__main__":
    App().mainloop()