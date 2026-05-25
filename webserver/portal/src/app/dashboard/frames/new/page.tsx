import Link from "next/link";

import LocationPicker from "@/components/LocationPicker";
import { createFrameAction } from "@/lib/actions";

const DISPLAYS = [
  { value: "inky_frame_7_spectra", label: "Inky Frame 7.3\" Spectra (800x480)" },
  { value: "inky_frame_7", label: "Inky Frame 7.3\" (800x480)" },
  { value: "inky_frame_5_7", label: "Inky Frame 5.7\" (600x448)" },
  { value: "inky_frame_4", label: "Inky Frame 4.0\" (640x400)" },
];

export default function NewFramePage() {
  return (
    <div className="mx-auto max-w-xl">
      <Link href="/dashboard" className="text-xs uppercase tracking-wide text-ink-soft hover:underline">&larr; Back to dashboard</Link>
      <h1 className="mt-3 font-display text-3xl">Add a new frame</h1>
      <p className="mt-2 text-sm text-ink-soft">
        Give your frame a unique short name (lowercase letters, numbers, dashes).
        Others will be able to send to it using this name.
      </p>
      <form action={createFrameAction} className="card mt-6 space-y-4">
        <div>
          <label className="label" htmlFor="name">Frame handle</label>
          <input id="name" name="name" className="input" required pattern="[a-z0-9\-]{3,64}" placeholder="kitchen-frame" />
          <p className="mt-1 text-xs text-ink-soft">Unique across all of Easel. 3-64 chars, lowercase.</p>
        </div>
        <div>
          <label className="label" htmlFor="display_name">Display name</label>
          <input id="display_name" name="display_name" className="input" required placeholder="The kitchen frame" />
        </div>
        <LocationPicker />
        <div>
          <label className="label" htmlFor="display_type">Display size</label>
          <select id="display_type" name="display_type" className="input">
            {DISPLAYS.map((d) => <option key={d.value} value={d.value}>{d.label}</option>)}
          </select>
        </div>
        <button type="submit" className="btn-primary w-full">Create & continue to SD setup</button>
      </form>
    </div>
  );
}
