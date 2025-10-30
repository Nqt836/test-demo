document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('questionForm');
    const mediaTypeSelect = document.getElementById('mediaType');
    const mediaFileInput = document.getElementById('mediaFile');
    const previewContainer = document.getElementById('previewContainer');

    // Handle media type change (we accept both image/video MIME types)
    mediaTypeSelect.addEventListener('change', function() {
        // keep accept open to both types so admins can upload any supported image/video
        mediaFileInput.accept = 'image/*,video/*';
        previewContainer.innerHTML = '';
        // disable file input if text-only selected
        if (this.value === 'text') {
            mediaFileInput.disabled = true;
        } else {
            mediaFileInput.disabled = false;
        }
    });

    // Preview media file (detect actual file type from the file MIME)
    mediaFileInput.addEventListener('change', function(e) {
        const file = e.target.files[0];
        previewContainer.innerHTML = '';
        if (!file) return;

        // Use object URL for faster preview
        const url = URL.createObjectURL(file);
        if (file.type && file.type.startsWith('video')) {
            const video = document.createElement('video');
            video.src = url;
            video.controls = true;
            video.style.maxWidth = '300px';
            previewContainer.appendChild(video);
        } else {
            const img = document.createElement('img');
            img.src = url;
            img.style.maxWidth = '300px';
            previewContainer.appendChild(img);
        }
    });

    // Handle form submission
    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const formData = new FormData(this);
        
        try {
            const response = await fetch('/admin/questions/upload', {
                method: 'POST',
                body: formData
            });
            
            const result = await response.json();
            
            if (response.ok) {
                alert('Question uploaded successfully!');
                form.reset();
                previewContainer.innerHTML = '';
            } else {
                alert('Error: ' + result.error);
            }
        } catch (error) {
            alert('Error uploading question: ' + error);
        }
    });
});