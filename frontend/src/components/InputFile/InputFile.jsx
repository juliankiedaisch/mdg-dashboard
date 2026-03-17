import React, { useRef, useState } from "react";
import "./InputFile.css";

export default function DragDropUpload({
  allowMultiple = false,
  allowedFormats = [] // z.B. [".xlsx", ".xls", ".pdf"]
}) {
  const inputRef = useRef(null);
  const [files, setFiles] = useState([]);
  const [progress, setProgress] = useState(0);
  const [isUploading, setIsUploading] = useState(false);

  // Prüfen, ob die Datei erlaubt ist
  const isFileAllowed = (file) => {
    if (allowedFormats.length === 0) return true; // keine Einschränkung
    const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
    return allowedFormats.includes(ext);
  };

  const handleFiles = (selectedFiles) => {
    const fileArray = allowMultiple
      ? Array.from(selectedFiles)
      : [selectedFiles[0]];

    // Nur erlaubte Dateien
    const validFiles = fileArray.filter(isFileAllowed);
    const invalidFiles = fileArray.filter(f => !isFileAllowed(f));

    if (invalidFiles.length > 0) {
      alert(
        `Folgende Dateien sind nicht erlaubt: ${invalidFiles
          .map(f => f.name)
          .join(", ")}`
      );
    }

    if (validFiles.length === 0) return;

    setFiles(validFiles);
    setProgress(0);
    simulateUpload();
  };

  const simulateUpload = () => {
    setIsUploading(true);
    let prog = 0;
    const interval = setInterval(() => {
      prog += 5;
      if (prog >= 100) {
        prog = 100;
        setIsUploading(false);
        clearInterval(interval);
      }
      setProgress(prog);
    }, 100);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFiles(e.dataTransfer.files);
      e.dataTransfer.clearData();
    }
  };

  const handleClick = () => inputRef.current.click();

  const handleChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFiles(e.target.files);
    }
  };

  const handleDragOver = (e) => e.preventDefault();

  // akzeptierte Formate für das native accept-Attribut
  const acceptAttr = allowedFormats.join(",");

  return (
    <div className="drag-drop-container">
      <div
        className="drop-area"
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onClick={handleClick}
      >
        {files.length > 0 ? (
          <ul className="file-list">
            {files.map((file, index) => (
              <li key={index}>{file.name}</li>
            ))}
          </ul>
        ) : (
          <span>
            Datei hierher ziehen oder klicken{" "}
            {allowMultiple && "(mehrere Dateien erlaubt)"}
          </span>
        )}
      </div>

      <input
        type="file"
        ref={inputRef}
        className="file-input"
        onChange={handleChange}
        multiple={allowMultiple}
        accept={acceptAttr}
      />

      {isUploading && (
        <div className="progress-bar">
          <div
            className="progress-fill"
            style={{ width: `${progress}%` }}
          ></div>
        </div>
      )}
    </div>
  );
}