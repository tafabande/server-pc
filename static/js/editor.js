// StreamDrop Document Editor using Quill.js
// Integrated with /api/docs for secure audit logging

let quill;
let currentDocPath = "";

function initEditor() {
    if (typeof Quill === 'undefined') {
        console.warn("Quill.js not loaded. Offline mode.");
        return;
    }
    quill = new Quill('#quill-editor', {
        theme: 'snow',
        placeholder: 'Start typing...',
        modules: {
            toolbar: [
                [{ 'header': [1, 2, 3, false] }],
                ['bold', 'italic', 'underline', 'strike'],
                [{ 'list': 'ordered'}, { 'list': 'bullet' }],
                ['link', 'clean']
            ]
        }
    });

    document.getElementById('closeEditorBtn').onclick = closeEditor;
    document.getElementById('saveEditorBtn').onclick = saveDocument;
}

// Open a document - matches user wiring request
async function openDocument(path, title) {
    currentDocPath = path;
    document.getElementById('editor-title').innerText = title || path.split('/').pop();
    
    // Fetch the raw text from the dedicated doc API (handles security & audit)
    try {
        const response = await fetch(`/api/docs/${encodeURIComponent(path)}`);
        if (response.ok) {
            const data = await response.json();
            if (quill) quill.setText(data.content); // Load text into editor
            document.getElementById('editor-container').classList.remove('hidden');
        } else {
            if (window.app && app.showToast) app.showToast("Failed to load document", true);
            else alert("Failed to load document");
        }
    } catch (err) {
        console.error("Editor error:", err);
    }
}

// Backward compatibility for app.js wiring
window.openEditor = openDocument;

// Save the document
async function saveDocument() {
    if (!currentDocPath || !quill) return;
    
    const text = quill.getText();
    const saveBtn = document.getElementById('saveEditorBtn');
    
    const originalText = saveBtn.innerText;
    saveBtn.innerText = "Saving...";
    saveBtn.disabled = true;

    try {
        const response = await fetch(`/api/docs/${encodeURIComponent(currentDocPath)}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content: text })
        });

        if (response.ok) {
            if (window.app && app.showToast) app.showToast("Document saved!");
            else console.log("Document saved!");
            
            saveBtn.innerText = "Saved!";
            setTimeout(() => {
                saveBtn.innerText = originalText;
                saveBtn.disabled = false;
            }, 1500);
        } else {
            throw new Error("Save failed");
        }
    } catch (err) {
        if (window.app && app.showToast) app.showToast("Failed to save", true);
        else alert("Failed to save");
        
        saveBtn.innerText = "Retry";
        saveBtn.disabled = false;
    }
}

function closeEditor() {
    document.getElementById('editor-container').classList.add('hidden');
    currentDocPath = "";
    if (quill) quill.setText('');
}

document.addEventListener('DOMContentLoaded', initEditor);
