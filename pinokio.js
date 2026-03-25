module.exports = {
  version: "6.0.0",
  title: "Silero VAD – Audiobook Cleaner",
  description: "Remove silences, ghost sounds and glitches from TTS audiobooks",
  menu: async function (kernel, info) {
    let installed = info.exists("env");
    let running   = info.running("start.json");

    if (running) {
      const url = info.local("url");
      return [
        { type: "label",  text: "🟢 Running" },
        { type: "button", text: "Open Web UI", href: url },
        {
          type: "button", text: "Stop",
          method: "shell.stop",
          params: { path: "start.json" }
        }
      ];
    }

    if (!installed) {
      return [
        {
          type: "button", text: "Install",
          method: "script.start",
          params: { path: "install.json" }
        }
      ];
    }

    return [
      {
        type: "button", text: "Start",
        method: "script.start",
        params: { path: "start.json" }
      },
      {
        type: "button", text: "Update",
        method: "script.start",
        params: { path: "update.json" }
      },
      {
        type: "button", text: "Reset",
        method: "script.start",
        params: { path: "reset.json" }
      }
    ];
  }
};
