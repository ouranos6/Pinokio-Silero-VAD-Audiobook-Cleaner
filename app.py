"""
Silero VAD – Audiobook Cleaner  (Pinokio edition)
Removes long silences, ghost sounds and glitches from TTS-generated audio.
Preserves original sample rate and bit depth.
"""

import os
import tempfile
from pathlib import Path

import gradio as gr
import torch
import torchaudio

# ── lazy-load the VAD model once ──────────────────────────────────────────────
_vad_model = None

def _get_model():
    global _vad_model
    if _vad_model is None:
        from silero_vad import load_silero_vad
        _vad_model = load_silero_vad()
    return _vad_model


# ── core processing ───────────────────────────────────────────────────────────
def clean_audio(
    audio_path,
    threshold,
    min_speech_ms,
    min_silence_ms,
    padding_ms,
    max_silence_keep_ms,
    progress=gr.Progress(),
):
    if audio_path is None:
        raise gr.Error("Please upload an audio file first.")

    from silero_vad import get_speech_timestamps

    VAD_SR = 16000  # Silero VAD requires 16 kHz

    # 1. Load at native sample rate (preserves quality)
    progress(0.05, "Loading audio…")
    waveform, orig_sr = torchaudio.load(audio_path)

    # 2. Convert to mono
    if waveform.shape[0] > 1:
        waveform = waveform.mean(dim=0, keepdim=True)

    # 3. Resample to 16 kHz for VAD analysis only
    progress(0.15, "Resampling for VAD…")
    if orig_sr != VAD_SR:
        resampler_down = torchaudio.transforms.Resample(orig_freq=orig_sr, new_freq=VAD_SR)
        wav_16k = resampler_down(waveform).squeeze(0)
    else:
        wav_16k = waveform.squeeze(0)

    original_duration = len(wav_16k) / VAD_SR

    # 4. Voice Activity Detection
    progress(0.35, "Running Voice Activity Detection…")
    model = _get_model()
    speech_ts_16k = get_speech_timestamps(
        wav_16k,
        model,
        threshold=float(threshold),
        min_speech_duration_ms=int(min_speech_ms),
        min_silence_duration_ms=int(min_silence_ms),
        speech_pad_ms=int(padding_ms),
        return_seconds=False,   # work in samples at 16 kHz
    )

    if not speech_ts_16k:
        raise gr.Error(
            "No speech detected. Try lowering the VAD threshold (e.g. 0.3)."
        )

    # 5. Scale timestamps from 16 kHz → original SR
    progress(0.55, "Mapping timestamps to original sample rate…")
    scale = orig_sr / VAD_SR
    wav_orig = waveform.squeeze(0)   # 1-D tensor at orig_sr

    # 6. Assemble output at original sample rate
    progress(0.70, "Assembling cleaned audio…")
    chunks = []
    if max_silence_keep_ms > 0:
        silence_pad = torch.zeros(int(max_silence_keep_ms * orig_sr / 1000))
        for i, ts in enumerate(speech_ts_16k):
            s = min(int(ts["start"] * scale), len(wav_orig))
            e = min(int(ts["end"]   * scale), len(wav_orig))
            chunks.append(wav_orig[s:e])
            if i < len(speech_ts_16k) - 1:
                chunks.append(silence_pad)
    else:
        for ts in speech_ts_16k:
            s = min(int(ts["start"] * scale), len(wav_orig))
            e = min(int(ts["end"]   * scale), len(wav_orig))
            chunks.append(wav_orig[s:e])

    cleaned = torch.cat(chunks)
    cleaned_duration = len(cleaned) / orig_sr
    removed_s = original_duration - cleaned_duration

    # 7. Save to a temp WAV
    progress(0.90, "Writing output file…")
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix="_cleaned.wav")
    tmp.close()
    torchaudio.save(tmp.name, cleaned.unsqueeze(0), orig_sr, format="wav")

    progress(1.00, "Done ✅")

    stats = (
        f"✅ **Processing complete**\n\n"
        f"| Metric | Value |\n"
        f"|---|---|\n"
        f"| Speech segments detected | **{len(speech_ts_16k)}** |\n"
        f"| Original duration | **{original_duration/60:.2f} min** ({original_duration:.1f} s) |\n"
        f"| Cleaned duration | **{cleaned_duration/60:.2f} min** ({cleaned_duration:.1f} s) |\n"
        f"| Removed | **{removed_s:.1f} s** ({100*removed_s/original_duration:.1f}%) |\n"
        f"| Original sample rate | **{orig_sr} Hz** |\n"
    )

    return tmp.name, stats


# ── Gradio UI ─────────────────────────────────────────────────────────────────
def build_ui():
    with gr.Blocks(title="Silero VAD – Audiobook Cleaner") as demo:
        gr.Markdown(
            "# 🎧 Silero VAD – Audiobook Cleaner\n"
            "Upload a TTS audiobook WAV, tune the parameters and click **Clean Audio**.\n"
            "Long silences, ghost sounds and glitches are removed while natural short pauses are preserved."
        )

        with gr.Row():
            # ── Left column : inputs ──────────────────────────────────────────
            with gr.Column(scale=1):
                audio_in = gr.Audio(
                    label="🎵 Input audio file",
                    type="filepath",
                )

                with gr.Accordion("⚙️ Parameters", open=True):
                    threshold = gr.Slider(
                        0.10, 0.99, value=0.50, step=0.01,
                        label="VAD Threshold",
                        info="↑ more strict (less false positives) · ↓ keeps borderline speech",
                    )
                    min_speech_ms = gr.Slider(
                        50, 2000, value=250, step=50,
                        label="Min speech segment (ms)",
                        info="Discard speech bursts shorter than this (removes isolated clicks/pops).",
                    )
                    min_silence_ms = gr.Slider(
                        100, 8000, value=1200, step=100,
                        label="Min silence to remove (ms)",
                        info="Only silences longer than this are considered for removal. "
                             "Set higher to keep more natural pauses.",
                    )
                    padding_ms = gr.Slider(
                        0, 500, value=80, step=10,
                        label="Speech padding (ms)",
                        info="Extra audio kept before and after each speech segment.",
                    )
                    max_silence_keep_ms = gr.Slider(
                        0, 3000, value=600, step=100,
                        label="Max silence kept between segments (ms)",
                        info="0 = weld segments together (no silence). "
                             ">0 = replace every gap with this fixed silence (recommended: 400–800 ms).",
                    )

                clean_btn = gr.Button("🚀 Clean Audio", variant="primary", size="lg")

            # ── Right column : outputs ────────────────────────────────────────
            with gr.Column(scale=1):
                audio_out = gr.Audio(
                    label="✨ Cleaned audio",
                    type="filepath",
                )
                stats_md = gr.Markdown(
                    "*Upload a file and click **Clean Audio** to start.*"
                )

        clean_btn.click(
            fn=clean_audio,
            inputs=[
                audio_in,
                threshold,
                min_speech_ms,
                min_silence_ms,
                padding_ms,
                max_silence_keep_ms,
            ],
            outputs=[audio_out, stats_md],
        )

    return demo


# ── entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7861))
    demo = build_ui()
    demo.launch(server_name="127.0.0.1", server_port=port, share=False)
