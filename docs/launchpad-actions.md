# Launchpad tiles that are not apps

A tile can run a keystroke or a command as well as launch an application.
Edit `~/.overwatch/apps.json`; six slots, in the order they appear on the
grid.

```json
[
  "Visual Studio Code",
  {"label": "Shot", "keys": "cmd+shift+4"},
  {"label": "Mic",  "run": ["pactl", "set-source-mute", "@DEFAULT_SOURCE@", "toggle"]},
  {"label": "Left", "keys": "ctrl+cmd+left"},
  "Terminal",
  {"label": "DND",  "run": ["shortcuts", "run", "Focus"]}
]
```

A plain string is an application, exactly as before — every existing file
keeps working untouched.

| Key | Meaning |
| --- | --- |
| `app` | an application, the same as a bare string |
| `keys` | a keystroke sent to whatever is frontmost |
| `run` | a command, as a **list** of arguments |
| `label` | what the tile says when it has no icon |
| `icon` | one of the compiled-in icon keys |

The daemon re-reads the file within a few seconds of a save. Nothing needs
restarting and the board needs no update.

## `run` is a list, never a string

```json
{"run": ["pactl", "set-sink-volume", "@DEFAULT_SINK@", "+5%"]}   ok
{"run": "pactl set-sink-volume @DEFAULT_SINK@ +5%"}              refused
```

The difference is the difference between running a program and running
whatever a shell makes of a line. A string is dropped and the slot is left
empty rather than interpreted.

## `keys` does not work everywhere

| Platform | Works | Needs |
| --- | --- | --- |
| macOS | yes | Accessibility permission, asked once |
| Linux, X11 | yes | `xdotool` |
| Linux, Wayland | **no** | — |

Wayland's design is that no application may synthesise input into another.
The tools that manage it want a root daemon and a uinput device, which is not
something a launcher gets to install on your behalf. On Wayland use `run`
tiles: almost everything a keystroke would have done has a command.

Check which session you have with `echo $XDG_SESSION_TYPE`.

Write `cmd` for the main modifier whichever machine you are on — it is
Command on macOS and Super on Linux. `ctrl`, `alt` and `shift` are
themselves. Named keys: `escape`, `tab`, `space`, `return`, `delete`, the
arrows, `home`, `end`, `pageup`, `pagedown`, `f1`–`f12`.

## Editing from the web page

The picker at `http://127.0.0.1:8730` only offers applications — it cannot
write a keystroke or a command. It will not destroy one either: it passes
every slot back unchanged and edits only the one you clicked.
