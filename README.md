# takeout-audit

**A command-line tool that looks at a Google Photos Takeout *before* you import
it, and reports how many photos and videos it could match to their `.json`
sidecar — and, for the rest, why it could not.**

When Google Photos writes a Takeout, the capture time does not live in the photo
itself. It lives in a small `.json` file placed next to it. Linking the two
again is mechanical, and it does not always work: long names are cut short on
the `.json` side, the `(1)` of a duplicate name sits in a different place on
each side, edited copies have no sidecar of their own, and an export split into
several zip files can put a photo and its sidecar in different parts.

This tool counts that, per file, before anything is imported. It does not fix
anything.

> **This tool's matching rules have not been verified against a real Google
> Takeout export. Results describe what this tool could match - not what your
> photo library will do.**

That line matters, so here is what it means in practice. The rules below were
written from publicly described naming behaviour, not from a Takeout that
someone measured. Where the rules fall short, the result always falls on the
same side: the file is reported as *not matched by this tool's rules*. So a
count here is a statement about this tool, not about your photos.

---

## What it does, and what it refuses to do

- **It never writes to the input.** Not one byte. Photos, sidecars and zip
  files are opened for reading only.
- **It never extracts a zip.** From an archive it reads the list of entry names
  and the contents of the `.json` entries, and nothing else. A Takeout can be
  hundreds of gigabytes; a tool you run to check things beforehand should not
  need room for a second copy.
- **It never reads the photo or video itself.** Only names and `.json` files.
- **It does not pick a winner when two candidates are equally good.** The row
  says `ambiguous_match` and both candidates are listed.
- **It does not repair, move, rename or import anything.** What to do next is
  your decision.

## Usage

All you need is **Python 3**. No external packages are used, and the tool never
connects to the network.

```
python3 -m takeout_audit ~/takeout                      # an extracted Takeout
python3 -m takeout_audit ~/takeout-001.zip ~/takeout-002.zip
python3 -m takeout_audit ~/takeout --report ~/audit.csv
python3 -m takeout_audit ~/takeout --list               # one line per file
```

Several zip files may be given at once. That is not a convenience: a photo and
its sidecar can end up in different parts of the same export, and they can only
be matched if both parts are read in the same run.

### Options

| Option | What it does |
|---|---|
| `--report PATH` | Write one row per media file to this CSV file. **The path may not be inside the input** |
| `--list` | Also print one row per media file to the screen (the default is the summary only) |
| `--version` | Print the version |
| `--help` | Print the usage |

### An example run

```
$ python3 -m takeout_audit ~/takeout
Takeout audit summary
count  what it means
-----  ----------------------------------------------------
6      media files looked at
2      matched to a .json and read a capture time (matched)
4      not matched by this tool's rules
1        no_sidecar
1        unmatched_by_known_rules
0        ambiguous_match
1        sidecar_without_time
1        unparsable_time
0        undecodable_name
2        matched by rule R1

This tool's matching rules have not been verified against a real Google Takeout
export. Results describe what this tool could match - not what your photo
library will do.
```

The CSV holds the detail, one row per media file:

```
media_path,media_key,json_path,rule,taken_time_utc,status,reason,candidates
/home/you/takeout/a/IMG_0001.jpg,a/IMG_0001.jpg,/home/you/takeout/a/IMG_0001.jpg.json,R1,2023-05-04T04:14:56Z,matched,,a/IMG_0001.jpg.json
/home/you/takeout/a/IMG_0002.jpg,a/IMG_0002.jpg,,,,not_matched,no_sidecar,
/home/you/takeout/a/IMG_0001-edited.jpg,a/IMG_0001-edited.jpg,,,,not_matched,unmatched_by_known_rules,a/IMG_0001.jpg.json
```

### The columns

| Column | What it holds |
|---|---|
| `media_path` | The file as it appeared in the input. For a zip, `<archive>::<entry>` |
| `media_key` | The path inside the Takeout, with `/` separators, normalised to Unicode NFC. **Matching and sorting use this, so the same Takeout gives the same answer whether it is zipped or extracted** |
| `json_path` | The sidecar that was matched, if one was |
| `rule` | Which rule matched (see below). Rules combine: `R3+R4` |
| `taken_time_utc` | The capture time read from the sidecar, in UTC |
| `status` | `matched` or `not_matched` |
| `reason` | Why it is not matched (see below). Empty when matched |
| `candidates` | Every sidecar that was near enough to consider, `\|` separated. Capped at eight, then `\|+N more` |

## What `reason` means

| `reason` | What it says |
|---|---|
| `no_sidecar` | **By this tool's proximity rule (see *The matching rules* below), no `.json` came near enough to this name to be a candidate.** It does not say that the photo has no sidecar: a sidecar that sits outside the reach of that rule is reported here too. Edited copies often land here |
| `unmatched_by_known_rules` | **By the same proximity rule a candidate was found, but no rule of this tool linked the two.** This one may well be a gap in the rules rather than a gap in your export. The candidates are listed in the row |
| `ambiguous_match` | Two or more candidates were equally good. **This tool does not choose** |
| `sidecar_without_time` | A sidecar was matched, but it holds no capture time |
| `unparsable_time` | A sidecar was matched, but its contents could not be read as a capture time |
| `undecodable_name` | The file name's character encoding could not be established — for example a zip entry stored without the UTF-8 flag, or a name on disk that is not valid UTF-8. **Not counted as a missing sidecar** |

A name that is not valid UTF-8 cannot be written to the CSV as it stands, so the
bytes that could not be decoded are written as `\xff`: a photo stored on disk as
`IMG_<ff><fe>02.jpg` appears as `IMG_\xff\xfe02.jpg`. **One such file does not
stop the run** — every other file in the same Takeout still gets its row.

`no_sidecar` and `unmatched_by_known_rules` are kept apart on purpose. Mixed
together, there is no way to tell a Takeout without a sidecar from a rule this
tool is missing.

## The matching rules

Candidates are looked for **in the same folder only**. A `.json` is a candidate
for a media file when one name is a prefix of the other, or when they share
their first eight characters. Among the candidates, these rules decide:

| Rule | Example |
|---|---|
| **R1** exact | `IMG_0001.jpg` ← `IMG_0001.jpg.json` |
| **R2** the `.json` name is cut short | `A_very_long_photo_name_0001.jpg` ← `A_very_long_photo_na.json` |
| **R3** the `(n)` sits elsewhere | `IMG_1234(1).jpg` ← `IMG_1234.jpg(1).json` |
| **R4** an inserted word | `IMG_5678.jpg` ← `IMG_5678.jpg.supplemental-metadata.json` |

Names are compared after Unicode NFC normalisation, and **upper and lower case
are kept apart**. Rules combine (`R4+R2` is an inserted word in a name that was
then cut short). When several candidates match at the same rank, the row becomes
`ambiguous_match`.

## If you open an issue

**Please do not paste your CSV into an issue as-is. It contains your file names
and timestamps. Replace them or attach only the counts.**

There is **no promise of support**. There is no commitment to answer issues.

This tool is **not affiliated with Google, Google Photos, immich or
PhotoPrism.** It reads files that those programs write or read, nothing more.

## License

MIT License (see `LICENSE`).

The source code and documentation of this tool were written with AI assistance
(Anthropic's Claude), then reviewed and published by the repository owner.
