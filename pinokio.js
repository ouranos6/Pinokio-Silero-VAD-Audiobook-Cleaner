module.exports = {
  version: "6.0.0",
  title: "Silero VAD – Audiobook Cleaner",
  description: "Remove silences, ghost sounds and glitches from TTS audiobooks",
  menu: async function (kernel, info) {
    let installed = info.exists("env");
    let running   = info.running("start.json");

    if (running) {
      return [
        { text: "Open Web UI", href: "http://127.0.0.1:7861", popout: true },
        { text: "Stop",        href: "stop.json" }
      ];
    }

    if (!installed) {
      return [
        { text: "Install", href: "install.json" }
      ];
    }

    return [
      { text: "Start",  href: "start.json"  },
      { text: "Update", href: "update.json" },
      { text: "Reset",  href: "reset.json"  }
    ];
  }
};
