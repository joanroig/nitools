# Release contents and licensing

## Content boundary

Release source contains NITools code, its build scripts, synthetic tests, original
project artwork and screenshots of NITools itself. It must not contain NI/Roland
software or artwork, kits, presets, sample libraries, preview audio, saved plug-in
states, activation data, product-catalog dumps, decompiler output or research
databases. The zero-valued PCM file at `resources/audio/.wav` is generated silence,
not a sample from a library.

The former bundled UPID catalog came from a third-party product-report dump with
no redistribution license recorded. It and its input dump are removed. Preview
export now reads product names from the user's local Service Center XML files;
unavailable names keep their existing library folder. The local metadata is not
copied into the app or uploaded.

Vendor software screenshots are removed. The maintainer requested that the
existing home screen be preserved, so its four music-service icons remain in
the local candidate. Their distribution terms/provenance still need review
before a public package or source release; their presence is not a claim that
the vendors license their marks or artwork under NITools' GPL. NITools artwork
has editable project sources under `docs/designs`.

Ignored `in/`, `out/`, `tmp/`, caches, `.venv/` and research folders are never
release inputs. Ignoring a file does not remove it if already tracked: inspect
the Git release tree as well as the package. Prior tags and Git history are not
rewritten by this release; the exclusions apply to the new release tree.

## Dependency obligations

Free software can still have copyright and redistribution conditions. NITools'
GPL license does not replace the licenses of Python, Qt, audio libraries or their
embedded dependencies. Packages need the applicable copyright/license notices
and corresponding-source access, including transitive native components.

For a binary release, the maintainer must:

1. Inventory the PyInstaller payload, not just `pyproject.toml`. Check every
   native library and generated data file against its installed distribution.
2. Include NITools' `LICENSE`, `THIRD_PARTY_NOTICES.md`, dependency license texts
   and a manifest of exact installed versions in each package.
3. Supply complete corresponding source and build instructions for covered
   components, with exact versions and accessible download locations beside the
   binary download. NITools source alone and generic project homepages are not
   sufficient for bundled GPL/LGPL dependencies. Check nested components such as
   JUCE/VST3, libsndfile codecs and Qt's third-party libraries.
4. Do not substitute a written source offer unless the maintainer can actually
   fulfill its requirements. Do not promise source availability that has not
   been established.
5. Exclude Microsoft runtime DLLs and the runtime installer from Windows
   packages. The launcher must detect missing/old prerequisites and offer a
   direct Microsoft download with signature verification. Test both detection
   and the app's use of the installed runtime, including NumPy's renamed DLLs.
6. Review each platform's actual archive and source tree before publishing.
   Automated filename checks are safeguards, not proof of authorship or a legal
   opinion.

The release workflow stops before version commits, builds or tags while
`packaging/release_review.json` is unapproved or contains pending items. Clear
those items only after the documented checks are complete and the maintainer
authorizes publication. Ordinary source pushes and local test builds do not run
the release workflow. Building an executable does not authorize its publication.

## References

- [GNU GPL version 3, especially sections 1 and 6](https://www.gnu.org/licenses/gpl-3.0.html)
- [Qt LGPL obligations](https://www.qt.io/development/open-source-lgpl-obligations)
- [PySide6 licensing](https://doc.qt.io/qtforpython-6/licenses.html)
- [Microsoft runtime downloads](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist)
- [Pedalboard license](https://github.com/spotify/pedalboard/blob/v0.9.26/LICENSE)

These checks address distribution of NITools. They do not establish that every
use of a proprietary library, reverse-engineering technique or exported sound is
permitted by its license or by the law in every jurisdiction.
