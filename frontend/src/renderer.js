// Application State
let scriptInfo = null;
let currentExecution = null;
let executionHistory = [];

// DOM Elements
const elements = {
    argumentsContainer: null,
    commandDisplay: null,
    executeBtn: null,
    stopBtn: null,
    outputContent: null,
    progressContainer: null,
    progressFill: null,
    progressText: null,
    prerequisitesStatus: null,
    historyModal: null,
    historyList: null,
    notifications: null
};

// Initialize the application
async function init() {
    console.log('🚀 Initializing SubtitleTranslatorAI GUI...');
    
    // Check if electronAPI is available
    if (!window.electronAPI) {
        console.error('❌ electronAPI not available - preload script may have failed');
        showNotification('Application failed to initialize: electronAPI not available', 'error');
        return;
    }
    console.log('✅ electronAPI is available');

    // Get DOM elements
    console.log('📋 Getting DOM elements...');
    Object.keys(elements).forEach(key => {
        const elementId = key.replace(/([A-Z])/g, '-$1').toLowerCase();
        elements[key] = document.getElementById(elementId === 'arguments-container' ? 'arguments-container' : elementId);
    });

    // Additional elements
    elements.argumentsContainer = document.getElementById('arguments-container');
    elements.commandDisplay = document.getElementById('command-display');
    elements.executeBtn = document.getElementById('execute-btn');
    elements.stopBtn = document.getElementById('stop-btn');
    elements.outputContent = document.getElementById('output-content');
    elements.progressContainer = document.getElementById('progress-container');
    elements.progressFill = document.getElementById('progress-fill');
    elements.progressText = document.getElementById('progress-text');
    elements.prerequisitesStatus = document.getElementById('prerequisites-status');
    elements.historyModal = document.getElementById('history-modal');
    elements.historyList = document.getElementById('history-list');
    elements.notifications = document.getElementById('notifications');

    // Check if all required elements were found
    const missingElements = Object.keys(elements).filter(key => !elements[key]);
    if (missingElements.length > 0) {
        console.error('❌ Missing DOM elements:', missingElements);
        showNotification(`Missing DOM elements: ${missingElements.join(', ')}`, 'error');
        return;
    }
    console.log('✅ All DOM elements found');

    // Setup event listeners
    console.log('🔗 Setting up event listeners...');
    setupEventListeners();
    console.log('✅ Event listeners setup complete');

    // Load script information
    console.log('📜 Loading script information...');
    await loadScriptInfo();

    // Load execution history
    console.log('📚 Loading execution history...');
    await loadExecutionHistory();

    // Listen for script output
    console.log('👂 Setting up script output listener...');
    window.electronAPI.onScriptOutput(handleScriptOutput);
    
    console.log('🎉 Initialization complete!');
}

// Setup event listeners
function setupEventListeners() {
    // Prerequisites button
    document.getElementById('prerequisites-btn').addEventListener('click', checkPrerequisites);

    // History button
    document.getElementById('history-btn').addEventListener('click', showHistory);
    document.getElementById('close-history').addEventListener('click', hideHistory);

    // Execution controls
    elements.executeBtn.addEventListener('click', executeScript);
    elements.stopBtn.addEventListener('click', stopScript);

    // Output controls
    document.getElementById('clear-output').addEventListener('click', clearOutput);
    document.getElementById('save-output').addEventListener('click', saveOutput);

    // Command copy
    document.getElementById('copy-command').addEventListener('click', copyCommand);

    // Modal backdrop clicks
    elements.historyModal.addEventListener('click', (e) => {
        if (e.target === elements.historyModal) {
            hideHistory();
        }
    });
}

// Load script information and generate UI
async function loadScriptInfo() {
    try {
        scriptInfo = await window.electronAPI.getScriptInfo();
        generateArgumentsUI();
        showNotification('Script information loaded successfully', 'success');
    } catch (error) {
        console.error('Error loading script info:', error);
        showNotification('Failed to load script information', 'error');
    }
}

// Generate dynamic UI for script arguments
function generateArgumentsUI() {
    if (!scriptInfo?.arguments) return;

    elements.argumentsContainer.innerHTML = '';

    scriptInfo.arguments.forEach(arg => {
        const group = document.createElement('div');
        group.className = 'argument-group';

        const label = document.createElement('label');
        label.className = 'argument-label';
        label.textContent = arg.flag || arg.description || 'Option';

        if (arg.description) {
            const desc = document.createElement('div');
            desc.className = 'argument-description';
            desc.textContent = arg.description;
            group.appendChild(desc);
        }

        const inputGroup = document.createElement('div');
        inputGroup.className = 'input-group';

        if (arg.type === 'file') {
            // File input
            const input = document.createElement('input');
            input.type = 'text';
            input.className = 'form-control';
            input.placeholder = 'Select file...';
            input.dataset.arg = arg.flag;
            input.dataset.required = arg.required || false;

            const browseBtn = document.createElement('button');
            browseBtn.type = 'button';
            browseBtn.className = 'btn btn-secondary btn-browse';
            browseBtn.innerHTML = `
                <svg viewBox="0 0 24 24" fill="currentColor">
                    <path d="M10 4H4c-1.11 0-2 .9-2 2v12c0 1.1.89 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z"/>
                </svg>
                Browse
            `;

            browseBtn.addEventListener('click', async () => {
                const filters = [];
                if (arg.accept) {
                    const ext = arg.accept.replace('.', '');
                    filters.push({ name: `${ext.toUpperCase()} Files`, extensions: [ext] });
                }
                filters.push({ name: 'All Files', extensions: ['*'] });

                const filePath = await window.electronAPI.selectFile({ filters });
                if (filePath) {
                    input.value = filePath;
                    updateCommand();
                }
            });

            input.addEventListener('input', updateCommand);

            inputGroup.appendChild(input);
            inputGroup.appendChild(browseBtn);
        } else if (arg.type === 'directory') {
            // Directory input
            const input = document.createElement('input');
            input.type = 'text';
            input.className = 'form-control';
            input.placeholder = 'Select directory...';
            input.dataset.arg = arg.flag;

            const browseBtn = document.createElement('button');
            browseBtn.type = 'button';
            browseBtn.className = 'btn btn-secondary btn-browse';
            browseBtn.innerHTML = `
                <svg viewBox="0 0 24 24" fill="currentColor">
                    <path d="M10 4H4c-1.11 0-2 .9-2 2v12c0 1.1.89 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z"/>
                </svg>
                Browse
            `;

            browseBtn.addEventListener('click', async () => {
                const dirPath = await window.electronAPI.selectDirectory();
                if (dirPath) {
                    input.value = dirPath;
                    updateCommand();
                }
            });

            input.addEventListener('input', updateCommand);

            inputGroup.appendChild(input);
            inputGroup.appendChild(browseBtn);
        } else if (arg.type === 'boolean') {
            // Checkbox input
            const checkGroup = document.createElement('div');
            checkGroup.className = 'form-check';

            const input = document.createElement('input');
            input.type = 'checkbox';
            input.id = `arg-${arg.flag}`;
            input.dataset.arg = arg.flag;

            const checkLabel = document.createElement('label');
            checkLabel.htmlFor = input.id;
            checkLabel.textContent = arg.flag;

            input.addEventListener('change', updateCommand);

            checkGroup.appendChild(input);
            checkGroup.appendChild(checkLabel);
            inputGroup.appendChild(checkGroup);
        } else {
            // Text input
            const input = document.createElement('input');
            input.type = 'text';
            input.className = 'form-control';
            input.placeholder = arg.description || 'Enter value...';
            input.dataset.arg = arg.flag;

            input.addEventListener('input', updateCommand);

            inputGroup.appendChild(input);
        }

        group.appendChild(label);
        group.appendChild(inputGroup);
        elements.argumentsContainer.appendChild(group);
    });

    updateCommand();
}

// Update command preview
function updateCommand() {
    if (!scriptInfo) return;

    const args = [];
    const inputs = elements.argumentsContainer.querySelectorAll('input');
    let hasRequiredFile = false;

    inputs.forEach(input => {
        const argFlag = input.dataset.arg;
        const isRequired = input.dataset.required === 'true';

        if (input.type === 'checkbox') {
            if (input.checked) {
                args.push(argFlag);
            }
        } else if (input.value.trim()) {
            if (argFlag === 'input') {
                hasRequiredFile = true;
                args.push(input.value.trim());
            } else {
                args.push(argFlag, input.value.trim());
            }
        } else if (isRequired && argFlag === 'input') {
            hasRequiredFile = false;
        }
    }

    const command = `${scriptInfo.scriptPath} ${args.join(' ')}`;
    elements.commandDisplay.textContent = command;

    // Enable/disable execute button based on required inputs
    elements.executeBtn.disabled = !hasRequiredFile;
}

// Execute the script
async function executeScript() {
    if (!scriptInfo || currentExecution) return;

    // Get arguments
    const args = [];
    const inputs = elements.argumentsContainer.querySelectorAll('input');
    let inputFile = '';

    inputs.forEach(input => {
        const argFlag = input.dataset.arg;

        if (input.type === 'checkbox') {
            if (input.checked) {
                args.push(argFlag);
            }
        } else if (input.value.trim()) {
            if (argFlag === 'input') {
                inputFile = input.value.trim();
                args.push(input.value.trim());
            } else {
                args.push(argFlag, input.value.trim());
            }
        }
    });

    if (!inputFile) {
        showNotification('Please select an input file', 'warning');
        return;
    }

    // Clear output and show progress
    clearOutput();
    elements.progressContainer.classList.remove('hidden');
    elements.executeBtn.classList.add('hidden');
    elements.stopBtn.classList.remove('hidden');

    // Update progress
    updateProgress(0, 'Starting execution...');

    try {
        currentExecution = {
            command: elements.commandDisplay.textContent,
            startTime: new Date(),
            args,
            inputFile
        };

        const result = await window.electronAPI.executeScript({
            args,
            workingDir: scriptInfo.backendPath
        });

        // Execution completed
        currentExecution.endTime = new Date();
        currentExecution.exitCode = result.exitCode;
        currentExecution.success = result.exitCode === 0;

        // Add to history
        executionHistory.unshift({ ...currentExecution });
        await saveExecutionHistory();

        // Show completion message
        if (result.exitCode === 0) {
            showNotification('Script executed successfully!', 'success');
            appendOutput('✅ Script execution completed successfully', 'success');
            updateProgress(100, 'Execution completed successfully');
        } else {
            showNotification(`Script failed with exit code: ${result.exitCode}`, 'error');
            appendOutput(`❌ Script execution failed with exit code: ${result.exitCode}`, 'error');
            updateProgress(100, `Execution failed (exit code: ${result.exitCode})`);
        }

    } catch (error) {
        console.error('Execution error:', error);
        showNotification('Script execution failed', 'error');
        appendOutput(`❌ Execution error: ${error.message}`, 'error');
        updateProgress(0, 'Execution failed');

        if (currentExecution) {
            currentExecution.endTime = new Date();
            currentExecution.error = error.message;
            currentExecution.success = false;
        }
    } finally {
        // Reset UI
        setTimeout(() => {
            elements.progressContainer.classList.add('hidden');
            elements.executeBtn.classList.remove('hidden');
            elements.stopBtn.classList.add('hidden');
            currentExecution = null;
        }, 2000);
    }
}

// Stop script execution
async function stopScript() {
    if (!currentExecution) return;

    try {
        await window.electronAPI.killScript();
        showNotification('Script execution stopped', 'warning');
        appendOutput('⚠️ Script execution was stopped by user', 'warning');
        updateProgress(0, 'Execution stopped');

        if (currentExecution) {
            currentExecution.endTime = new Date();
            currentExecution.stopped = true;
            currentExecution.success = false;
        }
    } catch (error) {
        showNotification('Failed to stop script', 'error');
    }
}

// Handle script output
function handleScriptOutput(data) {
    if (data.type === 'stdout') {
        appendOutput(data.data, 'stdout');
        
        // Try to extract progress information
        const progressMatch = data.data.match(/\[(\d+)\/(\d+)\]/);
        if (progressMatch) {
            const current = parseInt(progressMatch[1]);
            const total = parseInt(progressMatch[2]);
            const percentage = Math.round((current / total) * 100);
            updateProgress(percentage, `Step ${current} of ${total}`);
        }
    } else if (data.type === 'stderr') {
        appendOutput(data.data, 'stderr');
    }
}

// Append output to the display
function appendOutput(text, type = 'stdout') {
    // Remove placeholder if it exists
    const placeholder = elements.outputContent.querySelector('.output-placeholder');
    if (placeholder) {
        placeholder.remove();
    }

    const line = document.createElement('div');
    line.className = `output-line ${type}`;
    line.textContent = text;

    elements.outputContent.appendChild(line);
    elements.outputContent.scrollTop = elements.outputContent.scrollHeight;
}

// Clear output display
function clearOutput() {
    elements.outputContent.innerHTML = '<div class="output-placeholder">Ready to execute script. Configure options above and click Execute.</div>';
}

// Update progress bar
function updateProgress(percentage, text) {
    elements.progressFill.style.width = `${percentage}%`;
    elements.progressText.textContent = text;
}

// Check system prerequisites
async function checkPrerequisites() {
    elements.prerequisitesStatus.classList.remove('hidden');
    
    // Reset status
    const items = elements.prerequisitesStatus.querySelectorAll('.prerequisite-item');
    items.forEach(item => {
        item.className = 'prerequisite-item loading';
    });

    try {
        const checks = await window.electronAPI.checkPrerequisites();
        
        Object.keys(checks).forEach(check => {
            const item = elements.prerequisitesStatus.querySelector(`[data-check="${check}"]`);
            if (item) {
                item.className = `prerequisite-item ${checks[check] ? 'success' : 'error'}`;
            }
        });

        const allPassed = Object.values(checks).every(Boolean);
        showNotification(
            allPassed ? 'All prerequisites are met' : 'Some prerequisites are missing',
            allPassed ? 'success' : 'warning'
        );
    } catch (error) {
        showNotification('Failed to check prerequisites', 'error');
    }
}

// Show execution history
function showHistory() {
    elements.historyModal.classList.remove('hidden');
    renderHistory();
}

// Hide execution history
function hideHistory() {
    elements.historyModal.classList.add('hidden');
}

// Render execution history
function renderHistory() {
    if (executionHistory.length === 0) {
        elements.historyList.innerHTML = '<div class="output-placeholder">No execution history</div>';
        return;
    }

    elements.historyList.innerHTML = '';

    executionHistory.forEach((execution, index) => {
        const item = document.createElement('div');
        item.className = 'history-item';

        const command = document.createElement('div');
        command.className = 'history-command';
        command.textContent = execution.command;

        const meta = document.createElement('div');
        meta.className = 'history-meta';

        const duration = execution.endTime ? 
            Math.round((execution.endTime - execution.startTime) / 1000) : '?';

        const status = execution.success ? '✅ Success' : 
                      execution.stopped ? '⚠️ Stopped' : 
                      execution.error ? '❌ Error' : '❓ Unknown';

        meta.innerHTML = `
            <span>${execution.startTime.toLocaleString()}</span>
            <span>${status} (${duration}s)</span>
        `;

        item.appendChild(command);
        item.appendChild(meta);

        // Add click to rerun
        item.addEventListener('click', () => {
            // TODO: Implement rerun functionality
            hideHistory();
        });

        elements.historyList.appendChild(item);
    });
}

// Copy command to clipboard
async function copyCommand() {
    try {
        await navigator.clipboard.writeText(elements.commandDisplay.textContent);
        showNotification('Command copied to clipboard', 'success');
    } catch (error) {
        showNotification('Failed to copy command', 'error');
    }
}

// Save output to file
async function saveOutput() {
    try {
        const output = Array.from(elements.outputContent.querySelectorAll('.output-line'))
            .map(line => line.textContent)
            .join('\n');

        // Create blob and download
        const blob = new Blob([output], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `subtitletranslatorai-output-${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.txt`;
        a.click();
        URL.revokeObjectURL(url);

        showNotification('Output saved successfully', 'success');
    } catch (error) {
        showNotification('Failed to save output', 'error');
    }
}

// Show notification
function showNotification(message, type = 'info') {
    console.log(`📢 Notification [${type}]: ${message}`);
    
    // Fallback if notifications element is not available
    if (!elements.notifications) {
        console.warn('Notifications element not available, using alert fallback');
        if (type === 'error') {
            alert(`Error: ${message}`);
        } else {
            console.log(`Notification: ${message}`);
        }
        return;
    }
    
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;

    elements.notifications.appendChild(notification);

    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (notification.parentNode) {
            notification.remove();
        }
    }, 5000);
}

// Load execution history from storage
async function loadExecutionHistory() {
    try {
        const history = await window.electronAPI.getStoredValue('executionHistory');
        if (history) {
            executionHistory = history.map(item => ({
                ...item,
                startTime: new Date(item.startTime),
                endTime: item.endTime ? new Date(item.endTime) : null
            }));
        }
    } catch (error) {
        console.error('Failed to load execution history:', error);
    }
}

// Save execution history to storage
async function saveExecutionHistory() {
    try {
        // Keep only last 50 executions
        const historyToSave = executionHistory.slice(0, 50);
        await window.electronAPI.setStoredValue('executionHistory', historyToSave);
    } catch (error) {
        console.error('Failed to save execution history:', error);
    }
}

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', init); 