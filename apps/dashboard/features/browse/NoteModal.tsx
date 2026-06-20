"use client";

import { useState, useRef } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/Tabs";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { FileText, Link, Type, Folder } from "lucide-react";

interface NoteModalProps {
  open: boolean;
  onClose: () => void;
  onSubmitFiles: (files: File[]) => void;
  onSubmitUrl: (url: string) => void;
  onSubmitText: (text: string) => void;
}

export function NoteModal({
  open,
  onClose,
  onSubmitFiles,
  onSubmitUrl,
  onSubmitText,
}: NoteModalProps) {
  const [url, setUrl] = useState("");
  const [text, setText] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);

  const handleFileSubmit = () => {
    const files = fileInputRef.current?.files;
    if (files && files.length > 0) {
      onSubmitFiles(Array.from(files));
      onClose();
    }
  };

  const handleFolderSubmit = () => {
    const files = folderInputRef.current?.files;
    if (files && files.length > 0) {
      onSubmitFiles(Array.from(files));
      onClose();
    }
  };

  const handleUrlSubmit = () => {
    if (url.trim()) {
      onSubmitUrl(url.trim());
      setUrl("");
      onClose();
    }
  };

  const handleTextSubmit = () => {
    if (text.trim()) {
      onSubmitText(text.trim());
      setText("");
      onClose();
    }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Add Note</DialogTitle>
        </DialogHeader>

        <div className="px-6 pb-6 pt-4">
          <Tabs defaultValue="files" className="w-full">
            <TabsList className="grid w-full grid-cols-4">
              <TabsTrigger value="files" className="gap-1">
                <FileText className="size-3" />
                Files
              </TabsTrigger>
              <TabsTrigger value="url" className="gap-1">
                <Link className="size-3" />
                URL
              </TabsTrigger>
              <TabsTrigger value="text" className="gap-1">
                <Type className="size-3" />
                Text
              </TabsTrigger>
              <TabsTrigger value="folder" className="gap-1">
                <Folder className="size-3" />
                Folder
              </TabsTrigger>
            </TabsList>

            <TabsContent value="files" className="space-y-3 pt-3">
              <input
                ref={fileInputRef}
                type="file"
                multiple
                aria-label="Files to upload"
                className="block w-full text-sm file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-medium file:bg-primary file:text-primary-foreground hover:file:bg-primary/90"
              />
              <Button onClick={handleFileSubmit} className="w-full">
                Upload Files
              </Button>
            </TabsContent>

            <TabsContent value="url" className="space-y-3 pt-3">
              <Input
                aria-label="URL to save"
                placeholder="https://example.com/article"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleUrlSubmit()}
              />
              <p className="text-xs text-muted-foreground">
                Paste a URL to save into notes
              </p>
              <Button onClick={handleUrlSubmit} className="w-full">
                Save URL
              </Button>
            </TabsContent>

            <TabsContent value="text" className="space-y-3 pt-3">
              <textarea
                placeholder="Paste notes, snippets, or raw text..."
                aria-label="Text to save"
                value={text}
                onChange={(e) => setText(e.target.value)}
                rows={5}
                className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 resize-none"
              />
              <Button onClick={handleTextSubmit} className="w-full">
                Save as Note
              </Button>
            </TabsContent>

            <TabsContent value="folder" className="space-y-3 pt-3">
              <input
                ref={folderInputRef}
                type="file"
                {...({ webkitdirectory: "", directory: "" } as React.InputHTMLAttributes<HTMLInputElement>)}
                className="block w-full text-sm file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-medium file:bg-primary file:text-primary-foreground hover:file:bg-primary/90"
              />
              <p className="text-xs text-muted-foreground">
                Select a folder to ingest all files recursively
              </p>
              <Button onClick={handleFolderSubmit} className="w-full">
                Upload Folder
              </Button>
            </TabsContent>
          </Tabs>
        </div>
      </DialogContent>
    </Dialog>
  );
}
