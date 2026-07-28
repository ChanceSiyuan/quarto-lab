# QLab native helper

This macOS helper provides the authenticated local pipe and PTY used by the
Zotero extension to start the locally installed Codex CLI. The QLab build does
not use it to start Claude, SSH, a remote process, or an external API provider.

`scripts/build-universal.sh` builds and ad-hoc signs a universal Intel/Apple
Silicon executable at `native/dist/zoterochat-helper`. The XPI build invokes the
script automatically.
