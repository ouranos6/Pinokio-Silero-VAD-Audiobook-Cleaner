// Cross-platform PyTorch installer for Pinokio (uv)
module.exports = async (kernel) => {
  const platform = process.platform;   // "win32" | "darwin" | "linux"
  const arch     = process.arch;       // "x64"   | "arm64"

  let cmd;

  if (platform === "darwin" && arch === "arm64") {
    // Apple Silicon – CPU/MPS build (no CUDA index needed)
    cmd = "uv pip install torch torchaudio";
  } else if (platform === "darwin") {
    // Intel Mac
    cmd = "uv pip install torch torchaudio";
  } else {
    // Windows or Linux: prefer CUDA 12.1; falls back to CPU if unavailable
    cmd = "uv pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121";
  }

  return {
    run: [
      {
        method: "shell.run",
        params: {
          message: cmd,
          venv: "env"
        }
      }
    ]
  };
};
