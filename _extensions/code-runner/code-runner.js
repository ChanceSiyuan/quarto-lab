// Code Runner - Interactive code execution widget
(function() {
    'use strict';

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    async function runCode(button) {
        const container = button.closest('.code-runner');
        const codeInput = container.querySelector('.code-input');
        const outputDiv = container.querySelector('.code-runner-output');
        const runtime = container.dataset.runtime || 'python';
        
        const code = codeInput.value;
        
        // Update UI
        button.disabled = true;
        button.classList.add('running');
        button.textContent = '⏳ Running...';
        outputDiv.classList.add('visible');
        outputDiv.classList.remove('error', 'success');
        outputDiv.innerHTML = '<span class="info">Executing on server...</span>';
        
        try {
            const response = await fetch('/api/execute', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ code, runtime })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            
            // Format output
            let html = '';
            
            if (data.warning) {
                html += `<span class="info">⚠️ ${escapeHtml(data.warning)}</span>\n\n`;
            }
            
            if (data.output) {
                html += `<span class="stdout">${escapeHtml(data.output)}</span>`;
            }
            
            if (data.error) {
                html += `<span class="stderr">${escapeHtml(data.error)}</span>`;
                outputDiv.classList.add('error');
            } else {
                outputDiv.classList.add('success');
            }
            
            if (!data.output && !data.error) {
                html = '<span class="info">(No output)</span>';
            }
            
            outputDiv.innerHTML = html;
            
        } catch (error) {
            outputDiv.classList.add('error');
            outputDiv.innerHTML = `<span class="stderr">Connection Error: ${escapeHtml(error.message)}\n\nMake sure the API server is running:\ncd _server && ./start.sh</span>`;
        } finally {
            button.disabled = false;
            button.classList.remove('running');
            button.textContent = '▶ Run Code';
        }
    }

    // Initialize when DOM is ready
    function init() {
        // Attach click handlers to all run buttons
        document.querySelectorAll('.code-runner .run-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                runCode(this);
            });
        });

        // Allow Ctrl+Enter to run code
        document.querySelectorAll('.code-runner textarea').forEach(textarea => {
            textarea.addEventListener('keydown', (e) => {
                if (e.ctrlKey && e.key === 'Enter') {
                    e.preventDefault();
                    const btn = textarea.closest('.code-runner').querySelector('.run-btn');
                    if (btn && !btn.disabled) {
                        runCode(btn);
                    }
                }
            });
        });
    }

    // Run init when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
