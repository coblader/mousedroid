# Mouse Droid — CAD & CNC files

3D model, cut file, and fabrication notes for the MSE-6 body (the 1/4" plywood,
rib-and-skin shell cut on a Shaper Origin).

> **This folder covers only the body/shell.** For the whole robot — dimensions,
> electronics, power, wiring, firmware, and design rationale — see the master
> **`../BUILD.md`** (§3 BOM, §4 the body, §11 design decisions).

---

## Files in this folder

| File | What it is |
|---|---|
| `mouse-droid-panels.svg` | **The cut file.** 19 plywood pieces on a 48 × 31.9" sheet, in Shaper Origin color convention. |
| `mouse-droid.blend` | Full 3D model — assembly, flat cut layout, exploded view. Reference OBJ in collection `MSE6_Reference`. |
| `assembly-guide.html` | **Illustrated step-by-step assembly guide.** Open in a browser → print or save to PDF for the shop. |
| `renders/` | Exploded view + 6 progressive assembly-step images (also embedded in the guide). |
| `Mse-6/` | Geometrically-accurate reference model we matched the shape to (scale ×2 = inches). Not needed to build. |
| `comments*.png` | Annotated design-feedback sketches from the shaping rounds. |

Overall dimensions and assembled geometry are documented in `../BUILD.md` §4 — not
repeated here, to keep a single source of truth.

---

## Cut list

### CNC-cut 1/4" plywood — 19 pieces (`mouse-droid-panels.svg`)

| Piece | Qty | Notes |
|---|---|---|
| Bottom plate | 1 | 15.4 × 6.9"; edge notches at the 4 wheel stations |
| Ribs | 4 | Stations −7", −2.5", +2.5", +7" from center; lightening holes for wiring |
| Skirt sides | 2 | **Mirror pair** — cut 2 identical, flip one. Wheel notches in bottom edge |
| Skirt front / rear | 2 | Trapezoids; front and rear are different heights |
| Belt bands | 4 | Plain strips 1.125" wide (sides 16.85", ends 8.24") — table saw is fine |
| Shell sides | 2 | **Mirror pair** — cut 2 identical, flip one |
| Shell front / rear | 2 | Front = long 47° nose slope; rear = steep 71° facet |
| Top panel | 1 | Flat top |
| Greeble tray | 1 | Laminates on top of the top panel |

### Saw-cut 3/8" square dowel — belt rails (8 pieces; buy four 36" dowels)

| Piece | Qty | Length |
|---|---|---|
| Side rails (overshoot each end 0.68" — the bumper stubs) | 4 | 19-1/8" |
| Front / rear rails (fit between the side rails) | 4 | 8-1/4" |

*Optional:* miter the rail corners instead of butt-joining — add ~3/4" to each side
rail and cut all eight ends at 45°.

---

## Shaper Origin cutting notes

- **Color convention:** white fill + black stroke = exterior cut (cut outside the
  line); black fill = interior cut (cut inside). Gray text labels are reference only —
  skip them on the Origin.
- **Angled facet panels are drawn at their true unfolded size** (e.g. the front nose
  slope is longer than it looks in top view). Cut exactly as drawn and they wrap the
  ribs correctly.
- **Compound-angle joints** at the shell hips and skirt corners have a slight edge
  interference — bevel the mating edges with a block plane/sander, or fill the gap.
  The belt rails hide the waist joints.
- The 4 belt-band strips are simple rectangles — rip them on a table saw to save
  Shaper time if you prefer.

---

## Assembly

The full illustrated six-step sequence (skeleton → skirt → belt → running gear → lid →
fit) is in **`assembly-guide.html`** with a render for each step. Body construction
notes and the removable-lid service concept are in `../BUILD.md` §4.

## Re-rendering / editing

Open `mouse-droid.blend` in Blender. The `MouseDroid_Exploded` collection holds the
exploded view; step renders are produced by toggling object visibility per stage.
