import type { Metadata } from "next";
import { UploadForm } from "@/components/upload/UploadForm";
import { AskContext } from "@/components/ask/AskProvider";

export const metadata: Metadata = { title: "Upload a video" };

export default function Page() {
  return (
    <div className="mx-auto max-w-[720px] px-8 pb-24 pt-10 max-md:px-4">
      <AskContext page="upload" description="Uploading a recorded session" />
      <h1 className="wide text-[30px] font-semibold tracking-[-0.015em]">Upload a recorded session</h1>
      <p className="mt-2 max-w-[62ch] text-[15px] text-ink-2">
        Gemini watches the video and lists every step, addition and container it can see. The tube color is measured frame by frame,
        the color flip is detected locally, and the whole run is committed to the hash-chained record with a keyframe behind every event.
      </p>
      <div className="mt-8">
        <UploadForm />
      </div>
    </div>
  );
}
