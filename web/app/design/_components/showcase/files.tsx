"use client";

import { useEffect, useRef, useState } from "react";

import { FileDrop, type UploadItem } from "@/components/ui/file-drop";

import { Demo, DocSection } from "./doc";

const STATIC_ITEMS: UploadItem[] = [
  { id: "a", name: "passport-scan.pdf", size: 1_240_000, status: "uploading", progress: 62 },
  { id: "b", name: "right-to-work-share-code.pdf", size: 214_000, status: "scanning" },
  { id: "c", name: "employment-contract.docx", size: 88_000, status: "safe" },
  {
    id: "d",
    name: "photo-id.png",
    size: 3_400_000,
    status: "rejected",
    message: "A virus was found. The file was deleted.",
  },
];

/** Pretends to upload and scan, so the states can be seen. A name containing "virus" is rejected. */
function useFakeUploads() {
  const [items, setItems] = useState<UploadItem[]>([]);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);
  useEffect(() => {
    const pending = timers.current;
    return () => pending.forEach(clearTimeout);
  }, []);

  function add(files: File[]) {
    const fresh = files.map<UploadItem>((file, i) => ({
      id: `${Date.now()}-${i}-${file.name}`,
      name: file.name,
      size: file.size,
      status: "uploading",
      progress: 0,
    }));
    setItems((current) => [...current, ...fresh]);
    for (const item of fresh) {
      const update = (patch: Partial<UploadItem>, after: number) =>
        timers.current.push(
          setTimeout(
            () =>
              setItems((current) =>
                current.map((i) => (i.id === item.id ? { ...i, ...patch } : i)),
              ),
            after,
          ),
        );
      update({ progress: 40 }, 400);
      update({ progress: 85 }, 900);
      update({ status: "scanning", progress: undefined }, 1400);
      const bad = item.name.toLowerCase().includes("virus");
      update(
        bad
          ? { status: "rejected", message: "A virus was found. The file was deleted." }
          : { status: "safe" },
        2600,
      );
    }
  }
  return {
    items,
    add,
    remove: (id: string) => setItems((current) => current.filter((i) => i.id !== id)),
  };
}

export function FilesSection() {
  const uploads = useFakeUploads();
  return (
    <DocSection
      id="files"
      title="File upload"
      description="Drag files or choose them. Each one shows its progress, then 'Scanning…', then 'Safe' or 'Rejected'. The checks here only save time: the server checks every file again."
    >
      <Demo
        title="Interactive"
        note="Choose any file: it is not uploaded anywhere. Try a name containing 'virus', or a type that is not allowed."
      >
        <div className="w-full max-w-xl">
          <FileDrop
            label="Upload evidence"
            description="PDF, Word or an image, up to 10 MB."
            accept={[".pdf", ".docx", "image/*"]}
            multiple
            items={uploads.items}
            onFiles={uploads.add}
            onRemove={uploads.remove}
          />
        </div>
      </Demo>
      <Demo title="Every state" note="Uploading, scanning, safe and rejected.">
        <div className="w-full max-w-xl">
          <FileDrop
            label="Upload documents"
            accept={[".pdf"]}
            items={STATIC_ITEMS}
            onFiles={() => {}}
            onRemove={() => {}}
          />
        </div>
      </Demo>
      <Demo title="Disabled">
        <div className="w-full max-w-xl">
          <FileDrop label="Upload documents" items={[]} onFiles={() => {}} disabled />
        </div>
      </Demo>
    </DocSection>
  );
}
