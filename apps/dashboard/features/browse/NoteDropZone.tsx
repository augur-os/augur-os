"use client";

import { useState, useCallback, type DragEvent, type ReactNode } from "react";
import { Upload } from "lucide-react";

interface NoteDropZoneProps {
  onDrop: (files: File[]) => void;
  children: ReactNode;
}

export function NoteDropZone({ onDrop, children }: NoteDropZoneProps) {
  const [isDragOver, setIsDragOver] = useState(false);

  const handleDragEnter = useCallback((e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.currentTarget === e.target) {
      setIsDragOver(false);
    }
  }, []);

  const handleDragOver = useCallback((e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDrop = useCallback(
    (e: DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragOver(false);
      const files = Array.from(e.dataTransfer.files);
      if (files.length > 0) {
        onDrop(files);
      }
    },
    [onDrop]
  );

  return (
    <div
      className="relative"
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
    >
      {children}
      {isDragOver && (
        <div className="absolute inset-0 z-40 flex flex-col items-center justify-center bg-background/80 backdrop-blur-sm border-2 border-dashed border-primary rounded-lg">
          <Upload className="size-12 text-primary mb-3" />
          <p className="text-lg font-medium text-foreground">Drop to note</p>
          <p className="text-sm text-muted-foreground mt-1">PDF, DOCX, images, markdown, folders</p>
        </div>
      )}
    </div>
  );
}
