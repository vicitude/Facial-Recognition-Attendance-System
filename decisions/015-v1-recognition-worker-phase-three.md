# Decision 015: Recognition Worker Phase Three

## Status

Active.

## Scope

The real-time attendance page now runs YOLO/FaceNet inference in one short-lived
QThread per submitted frame. The Qt main thread keeps ownership of preview,
employee lookup, dialogs, and attendance feedback.

## Invariants

- At most one inference task is active.
- Frames arriving while inference is busy are dropped rather than queued.
- Stopping recognition invalidates submitted results through a generation token.
- Camera and window shutdown stop the timer, wait for the worker, and release the camera.
- Recognition algorithms, thresholds, database schema, service APIs, and legacy ui.py remain unchanged.

## Verification

`tests/test_anime_ui.py` passes 12 tests and skips one QMessageBox test because
the local Windows Qt offscreen plugin crashes while constructing the native dialog.
Python AST parsing and `git diff --check` also pass.

## ??????

- ??????? `_legacy_handle_recognition_name()`?????????????????? `frame`?`box` ???
- ??????? `_do_recognition()`?`_recognize_name()` ?????????????????
- ????????? 12 ????1 ????????????????

## ???????

This phase has not been verified end-to-end with a physical camera, model weights,
and a live MySQL database.
