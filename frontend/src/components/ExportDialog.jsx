import { useEffect, useRef, useState } from "react";
import { Copy, Download, X } from "lucide-react";
import { exportFile } from "../exportFile";

export default function ExportDialog({
  content,
  type,
  filename,
  description,
  onClose,
}) {
  const dialog = useRef(null);
  const [notice, setNotice] = useState("");
  const [preview, setPreview] = useState(false);
  useEffect(() => {
    const element = dialog.current;
    element.showModal();
    return () => element.close();
  }, []);
  async function copy() {
    try {
      await navigator.clipboard.writeText(content);
      setNotice(
        "File contents copied. You can paste them into a file or another tool.",
      );
    } catch {
      setPreview(true);
      setNotice(
        "Select the file contents below and copy them with Ctrl+C or Command+C.",
      );
    }
  }
  return (
    <dialog
      ref={dialog}
      className="workspace-dialog export-dialog"
      aria-label="Export selected data"
      onCancel={onClose}
      onClick={(event) => event.target === dialog.current && onClose()}
    >
      <div className="dialog-heading">
        <h2>Export selected data</h2>
        <button
          className="icon-btn"
          aria-label="Close export"
          onClick={onClose}
        >
          <X size={20} />
        </button>
      </div>
      <div className="export-content">
        <p>{description}</p>
        <b className="export-filename">{filename}</b>
        <div className="export-options">
          <button
            className="button primary"
            onClick={() => {
              exportFile(content, type, filename);
              setNotice(
                "Download requested. You can also copy the file contents.",
              );
            }}
          >
            <Download size={17} />
            Download file
          </button>
          <button className="button secondary" onClick={copy}>
            <Copy size={17} />
            Copy file contents
          </button>
        </div>
        {notice && (
          <p className="form-notice" role="status">
            {notice}
          </p>
        )}
        <details
          className="technical-details"
          open={preview}
          onToggle={(event) => setPreview(event.currentTarget.open)}
        >
          <summary>Preview file contents</summary>
          <textarea
            aria-label="Exported file content"
            value={content}
            readOnly
            rows={8}
          />
        </details>
      </div>
    </dialog>
  );
}
