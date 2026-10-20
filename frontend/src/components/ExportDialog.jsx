import { useState } from "react";
import { Copy, Download } from "lucide-react";
import Dialog from "./Dialog";
import { exportFile } from "../lib/exportFile.js";

/** Download or copy a JSON/CSV export, with a preview of exactly what is exported. */
export default function ExportDialog({ content, type, filename, description, onClose }) {
  const [notice, setNotice] = useState("");
  const [preview, setPreview] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(content);
      setNotice("Copied. Paste it into a file or another tool.");
    } catch {
      setPreview(true);
      setNotice("Copying is blocked here. Select the text below and press Ctrl+C (or Cmd+C).");
    }
  }

  return (
    <Dialog title="Export" onClose={onClose}>
      <div className="stack">
        <p>{description}</p>
        <code className="export-filename">{filename}</code>
        <div className="button-row">
          <button
            type="button"
            className="button button-primary"
            onClick={() => {
              exportFile(content, type, filename);
              setNotice("Download started.");
            }}
          >
            <Download size={16} />
            Download file
          </button>
          <button type="button" className="button" onClick={copy}>
            <Copy size={16} />
            Copy contents
          </button>
        </div>
        {notice && (
          <p className="form-notice" role="status">
            {notice}
          </p>
        )}
        <details className="details" open={preview} onToggle={(event) => setPreview(event.currentTarget.open)}>
          <summary>Preview the file</summary>
          <textarea className="export-preview" aria-label="Exported file contents" value={content} readOnly rows={8} />
        </details>
      </div>
    </Dialog>
  );
}
