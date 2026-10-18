Task: author ONE short test chapter for the Wisdom app installed at WISDOM_ENDPOINT=__ENDPOINT__ .

This is a QA run on a disposable test box. Chapter id: `qa-empty-hub`. Theme: Laozi on emptiness and usefulness,
"Laozi — The Empty Hub". It is a synthetic test chapter for a QA collection, so one source is enough.
The researched source is already prepared for you, verbatim, in `__WORK__/source-packet.json`
(a JSON array of {url, text}; Legge's 1891 public-domain translation of Tao Te Ching chapter 11).
Brief for the author: one compressed reading of chapter 11 for a modern reader; the argument is that usefulness
lives in the empty space that a made thing frames. Quote only from the supplied text.

Follow your installed `wisdom` skill exactly (load it with skill_view first) for how chapters are authored on this
installation. Work only inside `__WORK__` (use fresh paths under it for the toolkit, brief, output and receipt).
Do not import anything into the app. When done, reply with: the absolute paths of the chapter Markdown and the
receipt JSON, and the model id the receipt records in modelUsage. If the skill's route is unavailable, say so and stop.
