import { useState, useEffect, useRef } from "react";
import axios from "axios";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

const API = process.env.REACT_APP_BACKEND_URL;

export default function FormatoModule() {
  const [view, setView] = useState("home");
  const [file, setFile] = useState(null);
  const [pdfUrl, setPdfUrl] = useState(null);
  const [numPages, setNumPages] = useState(0);
  const [pageNumber, setPageNumber] = useState(1);
  const [editedText, setEditedText] = useState("");
  const [loading, setLoading] = useState(false);
  const [regenLoading, setRegenLoading] = useState(false);
  // Selection
  const [selectedText, setSelectedText] = useState("");
  const [selectionPos, setSelectionPos] = useState(null);
  // Chat
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [convertLoading, setConvertLoading] = useState("");
  // Merge PDFs
  const [mergeFiles, setMergeFiles] = useState([]);
  const [mergeLoading, setMergeLoading] = useState(false);
  const [dragIdx, setDragIdx] = useState(null);
  // Split PDF
  const [splitLoading, setSplitLoading] = useState(false);
  const splitInputRef = useRef(null);
  const mergeInputRef = useRef(null);
  const chatEndRef = useRef(null);
  const recognitionRef = useRef(null);
  const fileInputRef = useRef(null);
  const convertInputRef = useRef(null);
  const pdfViewerRef = useRef(null);

  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [chatMessages]);

  // Speech recognition
  useEffect(() => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SR) {
      const rec = new SR();
      rec.lang = "es-CL"; rec.continuous = false; rec.interimResults = false;
      rec.onresult = (e) => { setChatInput(prev => prev + " " + e.results[0][0].transcript); setIsListening(false); };
      rec.onend = () => setIsListening(false);
      rec.onerror = () => setIsListening(false);
      recognitionRef.current = rec;
    }
  }, []);

  // Listen for text selection on PDF viewer
  useEffect(() => {
    let debounce = null;
    const handleSelectionChange = () => {
      clearTimeout(debounce);
      debounce = setTimeout(() => {
        const sel = window.getSelection();
        const text = sel?.toString().trim();
        if (text && text.length > 2 && pdfViewerRef.current) {
          // Check if selection is inside PDF viewer
          const anchor = sel.anchorNode;
          const focus = sel.focusNode;
          const insideViewer = pdfViewerRef.current.contains(anchor) || pdfViewerRef.current.contains(focus);
          if (insideViewer) {
            try {
              const range = sel.getRangeAt(0);
              const rect = range.getBoundingClientRect();
              const viewerRect = pdfViewerRef.current.getBoundingClientRect();
              if (rect.width > 0) {
                setSelectedText(text);
                setSelectionPos({
                  top: rect.top - viewerRect.top + pdfViewerRef.current.scrollTop - 42,
                  left: Math.min(Math.max(rect.left - viewerRect.left + rect.width / 2, 80), viewerRect.width - 80)
                });
                return;
              }
            } catch {}
          }
        }
        // Only clear if not hovering the delete button
        if (!document.querySelector('.delete-sel-btn:hover')) {
          setSelectedText("");
          setSelectionPos(null);
        }
      }, 250);
    };
    document.addEventListener("selectionchange", handleSelectionChange);
    return () => { document.removeEventListener("selectionchange", handleSelectionChange); clearTimeout(debounce); };
  }, []);

  const toggleListening = () => {
    if (!recognitionRef.current) return alert("Tu navegador no soporta reconocimiento de voz");
    if (isListening) recognitionRef.current.stop();
    else { recognitionRef.current.start(); setIsListening(true); }
  };

  // Upload PDF
  const handleUploadPDF = async (e) => {
    const f = e.target.files[0];
    if (!f) return;
    setLoading(true);
    const fd = new FormData();
    fd.append("file", f);
    try {
      const r = await axios.post(`${API}/api/formato/upload`, fd);
      setFile(r.data);
      setEditedText(r.data.extracted_text || "");
      setPdfUrl(`${API}${r.data.file_url}`);
      setNumPages(r.data.page_count || 0);
      setPageNumber(1);
      setChatMessages([]);
      setSelectedText("");
      setSelectionPos(null);
      setView("editor");
    } catch (err) { alert("Error subiendo archivo"); }
    setLoading(false);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  // Delete selected text directly (cursor method)
  const deleteSelectedText = async () => {
    if (!selectedText || !editedText) return;
    setRegenLoading(true);

    // Remove selected text from editedText
    const newText = editedText.replace(selectedText, "").replace(/\n{3,}/g, "\n\n").trim();
    setEditedText(newText);
    setSelectedText("");
    setSelectionPos(null);
    window.getSelection()?.removeAllRanges();

    setChatMessages(prev => [...prev,
      { role: "system", text: `Texto borrado: "${selectedText.slice(0, 80)}${selectedText.length > 80 ? '...' : ''}"` }
    ]);

    await regeneratePreview(newText);
    setRegenLoading(false);
  };

  // AI Edit
  const sendEditInstruction = async (text) => {
    const msg = text || chatInput.trim();
    if (!msg || !file) return;
    setChatInput("");
    setChatMessages(prev => [...prev, { role: "user", text: msg }]);
    setChatLoading(true);
    try {
      const r = await axios.post(`${API}/api/formato/ai-edit`, {
        file_id: file.id, instruction: msg,
        current_text: editedText, session_id: `formato-${file.id}`,
      });
      if (r.data.edited_text && r.data.edited_text !== editedText) {
        setEditedText(r.data.edited_text);
        setChatMessages(prev => [...prev, { role: "assistant", text: r.data.summary || "Cambios aplicados" }]);
        await regeneratePreview(r.data.edited_text);
      } else {
        setChatMessages(prev => [...prev, { role: "assistant", text: r.data.summary || "No se detectaron cambios" }]);
      }
    } catch (err) {
      setChatMessages(prev => [...prev, { role: "assistant", text: "Error al procesar la instrucción" }]);
    }
    setChatLoading(false);
  };

  // Regenerate PDF from text
  const regeneratePreview = async (text) => {
    try {
      const r = await axios.post(
        `${API}/api/formato/regenerate-pdf`,
        { text: text || editedText, filename: file?.filename || "editado.pdf" },
        { responseType: "blob" }
      );
      const url = window.URL.createObjectURL(new Blob([r.data], { type: "application/pdf" }));
      setPdfUrl(prev => { if (prev?.startsWith("blob:")) window.URL.revokeObjectURL(prev); return url; });
      setPageNumber(1);
      // Recount pages
      try {
        const tempDoc = await pdfjs.getDocument(url).promise;
        setNumPages(tempDoc.numPages);
        tempDoc.destroy();
      } catch {}
    } catch (err) { console.error("Regen error:", err); }
  };

  // Download edited PDF
  const downloadEditedPDF = async () => {
    try {
      const r = await axios.post(
        `${API}/api/formato/regenerate-pdf`,
        { text: editedText, filename: file?.filename?.replace(/\.\w+$/, "_editado.pdf") || "editado.pdf" },
        { responseType: "blob" }
      );
      const url = window.URL.createObjectURL(new Blob([r.data], { type: "application/pdf" }));
      const a = document.createElement("a"); a.href = url;
      a.download = file?.filename?.replace(/\.\w+$/, "_editado.pdf") || "editado.pdf";
      document.body.appendChild(a); a.click(); a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) { alert("Error descargando PDF"); }
  };

  // File conversion
  const handleConvert = (type) => {
    const input = convertInputRef.current;
    if (!input) return;
    input.accept = type === "pdf-to-word" ? ".pdf" : type === "word-to-pdf" ? ".docx,.doc" : ".jpg,.jpeg,.png";
    input.dataset.convertType = type;
    input.click();
  };

  const onConvertFileSelected = async (e) => {
    const f = e.target.files[0];
    if (!f) return;
    const type = e.target.dataset.convertType;
    setConvertLoading(type);
    const fd = new FormData(); fd.append("file", f);
    const endpoints = { "pdf-to-word": "/api/formato/convert/pdf-to-word", "word-to-pdf": "/api/formato/convert/word-to-pdf", "image-to-word": "/api/formato/convert/image-to-word" };
    try {
      const r = await axios.post(`${API}${endpoints[type]}`, fd, { responseType: "blob" });
      const ext = type === "word-to-pdf" ? ".pdf" : ".docx";
      const mime = type === "word-to-pdf" ? "application/pdf" : "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
      const url = window.URL.createObjectURL(new Blob([r.data], { type: mime }));
      const a = document.createElement("a"); a.href = url; a.download = f.name.replace(/\.\w+$/, ext);
      document.body.appendChild(a); a.click(); a.remove(); window.URL.revokeObjectURL(url);
    } catch (err) { alert("Error en la conversión"); }
    setConvertLoading("");
    if (convertInputRef.current) convertInputRef.current.value = "";
  };

  const onDocLoadSuccess = ({ numPages: n }) => setNumPages(n);

  // ===== MERGE PDFs =====
  const handleMergeFilesSelect = (e) => {
    const files = Array.from(e.target.files || []);
    const allowed = files.filter(f => {
      const ext = f.name.toLowerCase();
      return ext.endsWith('.pdf') || ext.endsWith('.jpg') || ext.endsWith('.jpeg') || ext.endsWith('.png');
    });
    if (allowed.length < 1) return;
    setMergeFiles(prev => [...prev, ...allowed.map(f => ({ file: f, name: f.name, id: Date.now() + Math.random() }))]);
    if (mergeInputRef.current) mergeInputRef.current.value = "";
  };

  const removeMergeFile = (id) => setMergeFiles(prev => prev.filter(f => f.id !== id));

  const onDragStart = (idx) => setDragIdx(idx);
  const onDragOver = (e, idx) => { e.preventDefault(); };
  const onDrop = (e, dropIdx) => {
    e.preventDefault();
    if (dragIdx === null || dragIdx === dropIdx) return;
    setMergeFiles(prev => {
      const copy = [...prev];
      const [moved] = copy.splice(dragIdx, 1);
      copy.splice(dropIdx, 0, moved);
      return copy;
    });
    setDragIdx(null);
  };

  const executeMerge = async () => {
    if (mergeFiles.length < 2) return alert("Seleccione al menos 2 archivos");
    setMergeLoading(true);
    const fd = new FormData();
    mergeFiles.forEach(f => fd.append("files", f.file));
    try {
      const r = await axios.post(`${API}/api/formato/merge-pdfs`, fd, { responseType: "blob" });
      const url = window.URL.createObjectURL(new Blob([r.data], { type: "application/pdf" }));
      const a = document.createElement("a"); a.href = url; a.download = "documentos_unidos.pdf";
      document.body.appendChild(a); a.click(); a.remove(); window.URL.revokeObjectURL(url);
    } catch (err) { alert("Error uniendo PDFs"); }
    setMergeLoading(false);
  };

  // ===== SPLIT PDF =====
  const handleSplitPDF = () => splitInputRef.current?.click();
  const onSplitFileSelected = async (e) => {
    const f = e.target.files[0];
    if (!f) return;
    setSplitLoading(true);
    const fd = new FormData();
    fd.append("file", f);
    fd.append("mode", "all");
    try {
      const r = await axios.post(`${API}/api/formato/split-pdf`, fd, { responseType: "blob" });
      const url = window.URL.createObjectURL(new Blob([r.data], { type: "application/zip" }));
      const a = document.createElement("a"); a.href = url; a.download = f.name.replace(".pdf", "_dividido.zip");
      document.body.appendChild(a); a.click(); a.remove(); window.URL.revokeObjectURL(url);
    } catch (err) { alert("Error dividiendo PDF"); }
    setSplitLoading(false);
    if (splitInputRef.current) splitInputRef.current.value = "";
  };

  return (
    <div className="formato-module" data-testid="formato-module">
      <input type="file" ref={convertInputRef} style={{ display: "none" }} onChange={onConvertFileSelected} />
      <input type="file" ref={splitInputRef} accept=".pdf" style={{ display: "none" }} onChange={onSplitFileSelected} />

      {/* HOME */}
      {view === "home" && (
        <div className="formato-home" data-testid="formato-home">
          <div className="formato-section">
            <h3 className="formato-section-title"><i className="fa fa-file-pdf-o"></i> Editor de PDF con IA</h3>
            <p className="formato-desc">Suba un PDF para editarlo. Puede seleccionar texto con el cursor y borrarlo, o usar IA con texto/voz para indicar que borrar o modificar.</p>
            <div className="formato-upload-area" onClick={() => fileInputRef.current?.click()} data-testid="upload-pdf-editor">
              <i className="fa fa-cloud-upload formato-upload-icon"></i>
              <span>{loading ? "Subiendo..." : "Subir PDF para editar"}</span>
              <input type="file" ref={fileInputRef} accept=".pdf" onChange={handleUploadPDF} style={{ display: "none" }} />
            </div>
          </div>
          <div className="formato-section">
            <h3 className="formato-section-title"><i className="fa fa-exchange"></i> Conversión de Formatos</h3>
            <div className="formato-converters">
              <button className="formato-convert-btn" onClick={() => handleConvert("pdf-to-word")} disabled={!!convertLoading} data-testid="btn-pdf-to-word">
                <i className={`fa ${convertLoading === "pdf-to-word" ? "fa-spinner fa-spin" : "fa-file-pdf-o"}`}></i>
                <span className="convert-arrow">→</span><i className="fa fa-file-word-o"></i>
                <div className="convert-label">PDF a Word</div>
              </button>
              <button className="formato-convert-btn" onClick={() => handleConvert("word-to-pdf")} disabled={!!convertLoading} data-testid="btn-word-to-pdf">
                <i className={`fa ${convertLoading === "word-to-pdf" ? "fa-spinner fa-spin" : "fa-file-word-o"}`}></i>
                <span className="convert-arrow">→</span><i className="fa fa-file-pdf-o"></i>
                <div className="convert-label">Word a PDF</div>
              </button>
              <button className="formato-convert-btn" onClick={() => handleConvert("image-to-word")} disabled={!!convertLoading} data-testid="btn-image-to-word">
                <i className={`fa ${convertLoading === "image-to-word" ? "fa-spinner fa-spin" : "fa-file-image-o"}`}></i>
                <span className="convert-arrow">→</span><i className="fa fa-file-word-o"></i>
                <div className="convert-label">Imagen a Word</div>
              </button>
              <button className="formato-convert-btn" onClick={handleSplitPDF} disabled={splitLoading} data-testid="btn-split-pdf">
                <i className={`fa ${splitLoading ? "fa-spinner fa-spin" : "fa-scissors"}`}></i>
                <span className="convert-arrow">→</span><i className="fa fa-files-o"></i>
                <div className="convert-label">Dividir PDF</div>
              </button>
            </div>
          </div>

          {/* MERGE PDFs */}
          <div className="formato-section">
            <h3 className="formato-section-title"><i className="fa fa-files-o"></i> Unir PDFs e Imagenes</h3>
            <p className="formato-desc">Seleccione PDFs y/o imagenes (JPG, PNG). Las imagenes se convierten a PDF automaticamente al unir.</p>
            <input type="file" ref={mergeInputRef} accept=".pdf,.jpg,.jpeg,.png" multiple style={{ display: "none" }} onChange={handleMergeFilesSelect} />
            <div className="merge-area">
              {mergeFiles.length === 0 ? (
                <div className="formato-upload-area" onClick={() => mergeInputRef.current?.click()} data-testid="upload-merge-pdfs">
                  <i className="fa fa-files-o formato-upload-icon"></i>
                  <span>Seleccionar PDFs o imagenes para unir</span>
                </div>
              ) : (
                <>
                  <div className="merge-file-list" data-testid="merge-file-list">
                    {mergeFiles.map((f, idx) => (
                      <div key={f.id} className={`merge-file-item ${dragIdx === idx ? "dragging" : ""}`}
                        draggable onDragStart={() => onDragStart(idx)} onDragOver={(e) => onDragOver(e, idx)} onDrop={(e) => onDrop(e, idx)}
                        data-testid={`merge-file-${idx}`}>
                        <span className="merge-drag-handle"><i className="fa fa-bars"></i></span>
                        <span className="merge-file-num">{idx + 1}</span>
                        <i className={`fa ${/\.(jpg|jpeg|png)$/i.test(f.name) ? "fa-file-image-o" : "fa-file-pdf-o"}`} style={{ color: /\.(jpg|jpeg|png)$/i.test(f.name) ? "#4ade80" : "#60a5fa" }}></i>
                        <span className="merge-file-name">{f.name}</span>
                        <button className="merge-remove-btn" onClick={() => removeMergeFile(f.id)} data-testid={`merge-remove-${idx}`}>
                          <i className="fa fa-times"></i>
                        </button>
                      </div>
                    ))}
                  </div>
                  <div className="merge-actions">
                    <button className="docs-btn secondary" onClick={() => mergeInputRef.current?.click()} data-testid="btn-add-more-pdfs">
                      <i className="fa fa-plus"></i> Agregar mas
                    </button>
                    <button className="docs-btn primary" onClick={executeMerge} disabled={mergeFiles.length < 2 || mergeLoading} data-testid="btn-merge-pdfs">
                      <i className={`fa ${mergeLoading ? "fa-spinner fa-spin" : "fa-compress"}`}></i> {mergeLoading ? "Uniendo..." : `Unir ${mergeFiles.length} archivos`}
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* EDITOR */}
      {view === "editor" && file && (
        <div className="formato-editor" data-testid="formato-editor">
          <div className="formato-editor-header">
            <button className="docs-btn secondary" onClick={() => { setView("home"); setFile(null); setPdfUrl(null); setEditedText(""); }} data-testid="btn-back-formato">
              <i className="fa fa-arrow-left"></i> Volver
            </button>
            <h3 className="formato-file-name"><i className="fa fa-file-pdf-o"></i> {file.filename}</h3>
            <div className="formato-header-actions">
              {regenLoading && <span className="formato-regen-status"><i className="fa fa-spinner fa-spin"></i> Actualizando...</span>}
              <button className="docs-btn primary" onClick={downloadEditedPDF} data-testid="btn-download-edited">
                <i className="fa fa-download"></i> Descargar PDF
              </button>
            </div>
          </div>

          <div className="formato-editor-body">
            {/* PDF Viewer with selection */}
            <div className="formato-pdf-viewer" data-testid="pdf-viewer" ref={pdfViewerRef} style={{ position: "relative" }}>
              <div className="pdf-nav">
                <button disabled={pageNumber <= 1} onClick={() => setPageNumber(p => p - 1)} className="pdf-nav-btn"><i className="fa fa-chevron-left"></i></button>
                <span className="pdf-page-info">Página {pageNumber} de {numPages}</span>
                <button disabled={pageNumber >= numPages} onClick={() => setPageNumber(p => p + 1)} className="pdf-nav-btn"><i className="fa fa-chevron-right"></i></button>
              </div>
              <div className="pdf-canvas-wrapper">
                {pdfUrl && (
                  <Document file={pdfUrl} onLoadSuccess={onDocLoadSuccess} loading={<div className="pdf-loading"><i className="fa fa-spinner fa-spin"></i> Cargando PDF...</div>}>
                    <Page pageNumber={pageNumber} width={680} renderTextLayer={true} renderAnnotationLayer={false} />
                  </Document>
                )}
              </div>

              {/* Floating delete button on selection */}
              {selectedText && selectionPos && (
                <button
                  className="delete-sel-btn"
                  data-testid="btn-delete-selection"
                  style={{ top: selectionPos.top, left: selectionPos.left }}
                  onMouseDown={(e) => { e.preventDefault(); e.stopPropagation(); deleteSelectedText(); }}
                >
                  <i className="fa fa-trash"></i> Borrar selección
                </button>
              )}

              {/* Selection indicator */}
              {selectedText && (
                <div className="selection-indicator" data-testid="selection-indicator">
                  <i className="fa fa-scissors"></i> Seleccionado: "{selectedText.slice(0, 50)}{selectedText.length > 50 ? '...' : ''}"
                </div>
              )}
            </div>

            {/* AI Chat */}
            <div className="formato-chat" data-testid="formato-chat">
              <div className="formato-chat-header"><h4><i className="fa fa-magic"></i> Editor IA (texto/voz)</h4></div>
              <div className="formato-chat-messages">
                {chatMessages.length === 0 && (
                  <div className="formato-chat-welcome">
                    <i className="fa fa-magic"></i>
                    <p>Seleccione texto en el PDF y pulse "Borrar", o dé instrucciones por texto/voz.</p>
                    <div className="formato-suggestions">
                      <button onClick={() => sendEditInstruction("Borra el párrafo que habla de gasto operacional")} className="formato-suggestion">Borrar gasto operacional</button>
                      <button onClick={() => sendEditInstruction("Elimina la última sección del documento")} className="formato-suggestion">Eliminar última sección</button>
                      <button onClick={() => sendEditInstruction("Borra todas las firmas")} className="formato-suggestion">Borrar firmas</button>
                    </div>
                  </div>
                )}
                {chatMessages.map((msg, i) => (
                  <div key={i} className={`formato-chat-msg ${msg.role}`} data-testid={`formato-msg-${i}`}>
                    <div className="formato-msg-text">{msg.text}</div>
                  </div>
                ))}
                {chatLoading && <div className="formato-chat-msg assistant loading"><div className="chat-dots"><span /><span /><span /></div></div>}
                <div ref={chatEndRef} />
              </div>
              <div className="formato-chat-input">
                <button className={`chat-voice-btn ${isListening ? "listening" : ""}`} onClick={toggleListening} data-testid="btn-formato-voice">
                  <i className={`fa ${isListening ? "fa-stop-circle" : "fa-microphone"}`}></i>
                </button>
                <input type="text" placeholder={isListening ? "Escuchando..." : "Ej: Borrar párrafo de gastos..."}
                  value={chatInput} onChange={e => setChatInput(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && sendEditInstruction()}
                  className="chat-text-input" data-testid="formato-chat-input" />
                <button className="chat-send-btn" onClick={() => sendEditInstruction()} disabled={chatLoading} data-testid="btn-formato-send">
                  <i className="fa fa-paper-plane"></i>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
