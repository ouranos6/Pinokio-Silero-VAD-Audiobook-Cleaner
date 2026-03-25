import os
import shutil
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

import gradio as gr
import torch
import torchaudio

from resemble_enhance.enhancer.inference import denoise, enhance

_GRADIO_MAJOR = int(gr.__version__.split(".")[0])

device = (
    "cuda"
    if torch.cuda.is_available()
    else "mps"
    if getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available()
    else "cpu"
)


def _process_audio(path, solver, nfe, tau, denoising):
    solver = solver.lower()
    nfe = int(nfe)
    lambd = 0.9 if denoising else 0.1
    dwav, sr = torchaudio.load(path)
    dwav = dwav.mean(dim=0)
    wav1, new_sr = denoise(dwav, sr, device)
    wav2, new_sr = enhance(dwav, sr, device, nfe=nfe, solver=solver, lambd=lambd, tau=tau)
    return new_sr, wav1.cpu(), wav2.cpu()


def _fn(path, solver, nfe, tau, denoising):
    if not path:
        return None, None
    sr, wav1, wav2 = _process_audio(path, solver, nfe, tau, denoising)
    return (sr, wav1.numpy()), (sr, wav2.numpy())


def _fn_batch(paths, solver, nfe, tau, denoising):
    if not paths:
        return None, []
    normalized_paths = [p if isinstance(p, str) else getattr(p, "name", None) for p in paths]
    normalized_paths = [p for p in normalized_paths if p]
    if not normalized_paths:
        return None, []
    output_dir = Path(tempfile.mkdtemp(prefix="resemble-enhance-batch-"))
    summary = []
    try:
        for path in normalized_paths:
            sr, wav1, wav2 = _process_audio(path, solver, nfe, tau, denoising)
            src = Path(path)
            denoised_path = output_dir / f"{src.stem}_denoised.wav"
            enhanced_path = output_dir / f"{src.stem}_enhanced.wav"
            try:
                import soundfile as sf
                sf.write(denoised_path, wav1.clamp(-1, 1).numpy(), sr, subtype="PCM_16")
                sf.write(enhanced_path, wav2.clamp(-1, 1).numpy(), sr, subtype="PCM_16")
            except Exception:
                torchaudio.save(denoised_path, torch.as_tensor(wav1).clamp(-1, 1).unsqueeze(0).float(), sr)
                torchaudio.save(enhanced_path, torch.as_tensor(wav2).clamp(-1, 1).unsqueeze(0).float(), sr)
            summary.append([src.name, denoised_path.name, enhanced_path.name])
        archive_path = shutil.make_archive(str(output_dir), "zip", output_dir)
    finally:
        shutil.rmtree(output_dir, ignore_errors=True)
    return archive_path, summary


def _shared_controls():
    return [
        gr.Dropdown(choices=["Midpoint", "RK4", "Euler"], value="Midpoint", label="CFM ODE Solver"),
        gr.Slider(minimum=1, maximum=128, value=64, step=1, label="CFM Number of Function Evaluations"),
        gr.Slider(minimum=0, maximum=1, value=0.5, step=0.01, label="CFM Prior Temperature"),
        gr.Checkbox(value=False, label="Denoise Before Enhancement"),
    ]


def main():
    single_inputs = [gr.Audio(type="filepath", label="Input Audio"), *_shared_controls()]
    single_outputs = [
        gr.Audio(label="Output Denoised Audio"),
        gr.Audio(label="Output Enhanced Audio"),
    ]

    if _GRADIO_MAJOR >= 5:
        file_input = gr.File(
            file_count="multiple",
            file_types=[".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac"],
            label="Input Audio Files (multiple)",
        )
    else:
        file_input = gr.File(
            type="filepath",
            file_count="multiple",
            file_types=["audio"],
            label="Input Audio Files (multiple)",
        )

    batch_inputs = [file_input, *_shared_controls()]
    batch_outputs = [
        gr.File(label="Download Zipped Results"),
        gr.Dataframe(
            headers=["Input File", "Denoised Output", "Enhanced Output"],
            datatype=["str", "str", "str"],
            interactive=False,
            label="Output File Map",
        ),
    ]

    single_interface = gr.Interface(
        fn=_fn,
        title="Resemble Enhance",
        description="AI-driven audio enhancement, powered by Resemble AI.",
        inputs=single_inputs,
        outputs=single_outputs,
    )
    batch_interface = gr.Interface(
        fn=_fn_batch,
        title="Resemble Enhance (Batch)",
        description="Upload multiple audio files, download a zip with denoised + enhanced results.",
        inputs=batch_inputs,
        outputs=batch_outputs,
    )

    port = int(os.environ.get("PORT", 7860))
    gr.TabbedInterface(
        [single_interface, batch_interface], ["Single File", "Batch"]
    ).launch(server_name="127.0.0.1", server_port=port, share=True)

if __name__ == "__main__":
    demo = build_ui()
    demo.launch(server_name="127.0.0.1", server_port=7861, share=False)

