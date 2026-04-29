// StreamDrop Document Editor using Quill.js

let quill;
let currentEditingFile = null;

function initEditor() {
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

    document.getElementById('closeEditorBtn').addEventListener('click', closeEditor);
    document.getElementById('saveEditorBtn').addEventListener('click', saveDocument);
}

async function openEditor(filename) {
    currentEditingFile = filename;
    document.getElementById('editor-title').textContent = filename.split('/').pop();
    
    // Fetch content from backend
    try {
        const response = await fetch(`/api/docs/${encodeURIComponent(filename)}`);
        if (!response.ok) throw new Error('Failed to load document');
        
        const data = await response.json();
        const content = data.content;
        
        // Basic detection if it's markdown or txt.
        // For simplicity, we just set it as text, which Quill handles.
        // If it was HTML, we could use quill.clipboard.dangerouslyPasteHTML.
        quill.setText(content);
        
        document.getElementById('editor-container').classList.remove('hidden');
    } catch (err) {
        console.error('Error opening editor:', err);
        alert('Could not open document for editing.');
    }
}

function closeEditor() {
    document.getElementById('editor-container').classList.add('hidden');
    currentEditingFile = null;
    quill.setText('');
}

async function saveDocument() {
    if (!currentEditingFile) return;
    
    // For .txt and .md, we get the plain text.
    // In a more advanced implementation, we might convert Quill's Delta/HTML to Markdown.
    const content = quill.getText();
    
    const saveBtn = document.getElementById('saveEditorBtn');
    saveBtn.textContent = 'Saving...';
    saveBtn.disabled = true;
    
    try {
        const response = await fetch(`/api/docs/${encodeURIComponent(currentEditingFile)}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ content: content })
        });
        
        if (!response.ok) throw new Error('Failed to save document');
        
        // Show success briefly
        saveBtn.textContent = 'Saved!';
        setTimeout(() => {
            saveBtn.textContent = 'Save';
            saveBtn.disabled = false;
        }, 2000);
    } catch (err) {
        console.error('Error saving document:', err);
        alert('Could not save document.');
        saveBtn.textContent = 'Save';
        saveBtn.disabled = false;
    }
}

document.addEventListener('DOMContentLoaded', initEditor);
