# MG400 pen/text writing

- `mg400_writer.py`: robot connection, writing geometry, alphabet and motion logic.
- `mg400_writer_app.py`: Tkinter desktop interface; imports the core above.
- `mg400_writer_state.json`: saved app configuration, loaded beside the GUI with `Path(__file__).resolve().with_name(...)`.
- `legacy-versions/`: earlier core and app pair; preserved together.
- `archive-compiled/`: historical bytecode, not required at runtime.

Run the app from this folder with `python mg400_writer_app.py` after checking physical setup and configuration.
