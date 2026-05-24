"use client";

import { useCallback } from "react";

import FrameContentPreview from "@/components/FrameContentPreview";
import { previewInboxItemAction } from "@/lib/actions";

export default function InboxItemPreview({ itemId }: { itemId: string }) {
  const loadPreview = useCallback(() => previewInboxItemAction(itemId), [itemId]);

  return <FrameContentPreview className="mt-3" loadPreview={loadPreview} />;
}
