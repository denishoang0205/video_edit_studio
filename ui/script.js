/**
 * TikTok Video Studio Pro - Frontend Script
 * Handles Tab Switching, Light/Dark Mode, Drive Sync, Dashboard Summary & Table, Live Preview, and Batch Queue.
 */

let allVideosData = [];
let selectedVideos = new Set();
let isRunning = false;
let progressInterval = null;
let currentActiveTheme = 'dark'; // 'dark' or 'light'

document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    initTheme();
    initLivePreview();
    setupEventListeners();
    initAccountsManager();
    initPublishingTracker();
});

/* ==========================================================================
   1. Tab Navigation & Theme Engine
   ========================================================================== */
function initTabs() {
    const tabLinks = document.querySelectorAll('.tab-link');
    const tabContents = document.querySelectorAll('.tab-content');

    tabLinks.forEach(link => {
        link.addEventListener('click', () => {
            const targetTab = link.dataset.tab;
            
            // Toggle active classes
            tabLinks.forEach(l => l.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));
            
            link.classList.add('active');
            document.getElementById(targetTab).classList.add('active');

            if (targetTab === 'tab-publishing') {
                fetchPublishingMatrix();
            }
        });
    });
}

function initTheme() {
    const themeToggleBtn = document.getElementById('theme-toggle');
    
    // Check OS window preference
    const prefersLight = window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches;
    const storedTheme = localStorage.getItem('studio-theme');
    
    if (storedTheme === 'light' || (!storedTheme && prefersLight)) {
        setTheme('light');
    } else {
        setTheme('dark');
    }

    themeToggleBtn.addEventListener('click', () => {
        if (currentActiveTheme === 'dark') {
            setTheme('light');
        } else {
            setTheme('dark');
        }
    });

    // Listen to OS color scheme changes
    window.matchMedia('(prefers-color-scheme: light)').addEventListener('change', e => {
        if (!localStorage.getItem('studio-theme')) {
            setTheme(e.matches ? 'light' : 'dark');
        }
    });
}

function setTheme(theme) {
    currentActiveTheme = theme;
    localStorage.setItem('studio-theme', theme);
    
    const icon = document.querySelector('#theme-toggle i');
    if (theme === 'light') {
        document.body.classList.add('theme-light');
        icon.className = 'fa-solid fa-sun';
        icon.style.color = '#eab308';
    } else {
        document.body.classList.remove('theme-light');
        icon.className = 'fa-solid fa-moon';
        icon.style.color = '#8b5cf6';
    }
}

/* ==========================================================================
   2. Live Preview & Interactive Studio Controls
   ========================================================================== */
function initLivePreview() {
    const ratioInputs = document.querySelectorAll('input[name="aspect_ratio"]');
    const mockupCanvas = document.getElementById('mockup-canvas');
    const previewRatioLabel = document.getElementById('preview-ratio-label');
    const boxStyleSelect = document.getElementById('banner-box-style');
    const fontSelect = document.getElementById('banner-font');
    const fontSizeInput = document.getElementById('banner-font-size');
    const fontSizeVal = document.getElementById('font-size-val');
    const previewTextInput = document.getElementById('preview-text-input');
    const canvasBanner = document.getElementById('canvas-banner');
    const canvasBannerText = document.getElementById('canvas-banner-text');
    const effectBlur = document.getElementById('effect-blur-bg');
    const canvasBgBlur = document.getElementById('canvas-bg-blur');
    const bannerPosition = document.getElementById('banner-position');

    // Ratio Switcher
    ratioInputs.forEach(input => {
        input.addEventListener('change', (e) => {
            document.querySelectorAll('.ratio-card').forEach(c => c.classList.remove('active'));
            e.target.closest('.ratio-card').classList.add('active');
            
            const val = e.target.value;
            mockupCanvas.className = `mockup-canvas ratio-${val.replace(':', '-')}-canvas`;
            previewRatioLabel.textContent = `${val} Canvas`;
        });
    });

    // Box Style
    boxStyleSelect.addEventListener('change', (e) => {
        canvasBanner.className = `canvas-banner banner-${e.target.value}`;
    });

    // Font
    const fontMap = {
        "Poppins-Bold": "Poppins, sans-serif",
        "Montserrat-Bold": "Montserrat, sans-serif",
        "Arial-Bold": "Arial, sans-serif",
        "BeVietnamPro-Bold": "'Be Vietnam Pro', sans-serif"
    };
    const updateFontFamily = () => {
        const family = fontMap[fontSelect.value] || "sans-serif";
        canvasBanner.style.fontFamily = family;
        if (canvasBannerText) {
            canvasBannerText.style.fontFamily = family;
        }
    };
    fontSelect.addEventListener('change', updateFontFamily);
    updateFontFamily(); // Áp dụng ngay khi khởi tạo trang

    // Font Size
    fontSizeInput.addEventListener('input', (e) => {
        fontSizeVal.textContent = `${e.target.value}px`;
        // Scale proportionally in miniature canvas
        const scaledSize = Math.max(9, Math.round(e.target.value * 0.22));
        canvasBanner.style.fontSize = `${scaledSize}px`;
    });

    // Text Live Sync
    previewTextInput.addEventListener('input', (e) => {
        canvasBannerText.textContent = e.target.value.toUpperCase() || "SAMPLE VIDEO TITLE";
    });

    // Blur Background Toggle
    effectBlur.addEventListener('change', (e) => {
        canvasBgBlur.style.opacity = e.target.checked ? '0.85' : '0.1';
    });

    // Banner Position
    bannerPosition.addEventListener('change', (e) => {
        const pos = e.target.value;
        if (pos === 'top') {
            canvasBanner.style.top = '18px';
            canvasBanner.style.bottom = 'auto';
        } else if (pos === 'center') {
            canvasBanner.style.top = '40%';
            canvasBanner.style.bottom = 'auto';
        } else if (pos === 'bottom') {
            canvasBanner.style.top = 'auto';
            canvasBanner.style.bottom = '18px';
        }
    });

    // Hàm đồng bộ tất cả các thuộc tính xem trước trên canvas khi tải trang
    const syncAllPreview = () => {
        updateFontFamily();
        
        // Đồng bộ cỡ chữ
        fontSizeVal.textContent = `${fontSizeInput.value}px`;
        const scaledSize = Math.max(9, Math.round(fontSizeInput.value * 0.22));
        canvasBanner.style.fontSize = `${scaledSize}px`;
        
        // Đồng bộ kiểu hộp banner
        canvasBanner.className = `canvas-banner banner-${boxStyleSelect.value}`;
        
        // Đồng bộ văn bản mẫu
        canvasBannerText.textContent = previewTextInput.value.toUpperCase() || "SAMPLE VIDEO TITLE";
        
        // Đồng bộ độ mờ nền
        canvasBgBlur.style.opacity = effectBlur.checked ? '0.85' : '0.1';
        
        // Đồng bộ vị trí banner
        const pos = bannerPosition.value;
        if (pos === 'top') {
            canvasBanner.style.top = '18px';
            canvasBanner.style.bottom = 'auto';
        } else if (pos === 'center') {
            canvasBanner.style.top = '40%';
            canvasBanner.style.bottom = 'auto';
        } else if (pos === 'bottom') {
            canvasBanner.style.top = 'auto';
            canvasBanner.style.bottom = '18px';
        }
    };
    syncAllPreview();
}

/* ==========================================================================
   3. Event Listeners & Core Handlers
   ========================================================================== */
function setupEventListeners() {
    const btnScan = document.getElementById('btn-scan-source');
    const btnRefresh = document.getElementById('btn-refresh-data');
    const chkSelectAll = document.getElementById('chk-select-all');
    const btnStart = document.getElementById('btn-start-processing');
    const btnStop = document.getElementById('btn-stop-processing');
    const btnOpenDest = document.getElementById('btn-open-dest-folder');
    const linkOpenGDriveTab = document.getElementById('link-open-gdrive-dest-tab');
    const filterBtns = document.querySelectorAll('.filter-btn');
    const selectFilter = document.getElementById('select-folder-filter');

    btnScan.addEventListener('click', () => {
        const path = document.getElementById('source-drive-link').value.trim();
        if (path) scanSourcePath(path);
    });

    btnRefresh.addEventListener('click', () => {
        const path = document.getElementById('source-drive-link').value.trim();
        if (path) scanSourcePath(path);
        fetchResults();
        fetchPublishingMatrix();
    });

    chkSelectAll.addEventListener('change', (e) => {
        const checkboxes = document.querySelectorAll('.video-checkbox');
        checkboxes.forEach(cb => {
            const isEdited = cb.dataset.edited === 'true';
            // Chỉ áp dụng chọn/bỏ chọn cho các video chưa edit
            if (!isEdited) {
                cb.checked = e.target.checked;
                const path = cb.dataset.path;
                if (e.target.checked) {
                    selectedVideos.add(path);
                } else {
                    selectedVideos.delete(path);
                }
            }
        });
        updateSelectedCount();
    });

    filterBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            filterBtns.forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            filterVideoTree(e.target.dataset.filter);
        });
    });

    btnStart.addEventListener('click', startBatchProcessing);
    btnStop.addEventListener('click', stopProcessing);

    const openDestFolderAction = () => {
        const dest = document.getElementById('dest-drive-link').value.trim();
        if (dest.startsWith('http')) {
            window.open(dest, '_blank');
        } else {
            fetch('/api/open_folder', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path: dest })
            });
        }
    };

    btnOpenDest.addEventListener('click', openDestFolderAction);
    linkOpenGDriveTab.addEventListener('click', (e) => {
        e.preventDefault();
        openDestFolderAction();
    });

    const btnRefreshFinished = document.getElementById('btn-refresh-finished');
    if (btnRefreshFinished) {
        btnRefreshFinished.addEventListener('click', () => {
            fetchResults();
        });
    }

    const btnDeleteAllFinished = document.getElementById('btn-delete-all-finished');
    if (btnDeleteAllFinished) {
        btnDeleteAllFinished.addEventListener('click', () => {
            deleteAllFinishedVideos();
        });
    }

    // Table Select folder filtering
    selectFilter.addEventListener('change', (e) => {
        renderDashboardTable(allVideosData, e.target.value);
    });

    // Modal close
    const closeModalAction = () => {
        const modal = document.getElementById('video-modal');
        modal.classList.add('hidden');
        const player = document.getElementById('modal-video-player');
        if (player) {
            player.pause();
            player.removeAttribute('src');
            player.load();
        }
    };
    document.getElementById('btn-close-modal').addEventListener('click', closeModalAction);
    document.getElementById('video-modal').addEventListener('click', (e) => {
        if (e.target.id === 'video-modal') closeModalAction();
    });

    // Folder Pickers (Tkinter integration)
    const btnPickSource = document.getElementById('btn-pick-source');
    const btnPickDest = document.getElementById('btn-pick-dest');
    
    const pickFolderAction = async (inputId) => {
        try {
            const res = await fetch('/api/select_folder', { method: 'POST' });
            const data = await res.json();
            if (data.folder_path) {
                document.getElementById(inputId).value = data.folder_path;
            }
        } catch (err) {
            console.error('Error selecting folder:', err);
        }
    };
    
    btnPickSource.addEventListener('click', (e) => {
        e.preventDefault();
        pickFolderAction('source-drive-link');
    });
    
    btnPickDest.addEventListener('click', (e) => {
        e.preventDefault();
        pickFolderAction('dest-drive-link');
    });
}

/* ==========================================================================
   4. Scan Drive & Folder Parser
   ========================================================================== */
async function scanSourcePath(sourcePath) {
    const container = document.getElementById('video-tree-container');
    container.innerHTML = `
        <div class="empty-state">
            <i class="fa-solid fa-circle-notch fa-spin"></i>
            <p>Reading source directory and analyzing files...</p>
        </div>
    `;

    try {
        const destPath = document.getElementById('dest-drive-link').value.trim();
        const res = await fetch('/api/scan_source', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ source: sourcePath, dest: destPath })
        });
        const data = await res.json();

        if (data.error) {
            container.innerHTML = `
                <div class="empty-state" style="color: var(--danger);">
                    <i class="fa-solid fa-triangle-exclamation"></i>
                    <p>${data.error}</p>
                </div>
            `;
            return;
        }

        allVideosData = data.folders || [];
        
        // Render Studio Explorer Tree
        renderVideoTree(allVideosData);
        updateExplorerStats(allVideosData);
        
        // Render Dashboard Statistics
        updateDashboardSummary(allVideosData);
        populateFolderFilterDropdown(allVideosData);
        renderDashboardTable(allVideosData, 'all');

        fetchResults();
        if (typeof fetchAccountsData === 'function') {
            fetchAccountsData();
        }
    } catch (err) {
        container.innerHTML = `
            <div class="empty-state" style="color: var(--danger);">
                <i class="fa-solid fa-triangle-exclamation"></i>
                <p>Cannot connect to server: ${err.message}</p>
            </div>
        `;
    }
}

function renderVideoTree(folders) {
    const container = document.getElementById('video-tree-container');
    if (!folders || folders.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <i class="fa-solid fa-folder-open"></i>
                <p>No videos found.</p>
            </div>
        `;
        return;
    }

    container.innerHTML = '';

    folders.forEach(folder => {
        const folderEl = document.createElement('div');
        folderEl.className = 'folder-group';

        const totalVids = folder.videos.length;
        const editedVids = folder.videos.filter(v => v.edited).length;

        folderEl.innerHTML = `
            <div class="folder-header">
                <div class="folder-left">
                    <i class="fa-solid fa-folder-open text-primary"></i>
                    <span>${folder.name}</span>
                </div>
                <span class="badge badge-info">${editedVids}/${totalVids} Edited</span>
            </div>
            <div class="folder-items-list"></div>
        `;

        const listEl = folderEl.querySelector('.folder-items-list');

        folder.videos.forEach(video => {
            const itemEl = document.createElement('div');
            itemEl.className = `video-tree-item ${video.edited ? 'is-edited' : 'is-unedited'}`;

            const badgeHtml = video.edited 
                ? '<span class="badge-status edited"><i class="fa-solid fa-check"></i> Edited</span>'
                : '<span class="badge-status unedited">⚪ Unedited</span>';

            itemEl.innerHTML = `
                <div class="video-item-left">
                    <label class="custom-checkbox">
                        <input type="checkbox" class="video-checkbox" data-path="${video.path}" data-title="${video.title}" data-edited="${video.edited}" data-channel="${folder.name}">
                        <span class="checkmark"></span>
                    </label>
                    <span class="video-title-truncate" title="${video.title}">${video.title}</span>
                </div>
                <div>${badgeHtml}</div>
            `;

            // Checkbox event
            const cb = itemEl.querySelector('.video-checkbox');
            cb.addEventListener('change', async (e) => {
                if (e.target.checked) {
                    if (video.edited) {
                        if (video.is_finished_only) {
                            alert(`Video "${video.title}" đã được xuất thành phẩm hoàn tất trong thư mục Output!\n\n(Tệp video gốc đã được tự động dọn dẹp để tiết kiệm dung lượng đĩa. Nếu bạn muốn biên tập lại, hãy copy tệp video gốc mới vào thư mục Kênh).`);
                            e.target.checked = false;
                            return;
                        }

                        const shouldReEdit = confirm(
                            `Video này đã có bản thành phẩm được tạo trước đó!\n\nBạn có muốn XÓA bản thành phẩm cũ để biên tập lại video:\n"${video.title}" không?`
                        );
                        if (shouldReEdit) {
                            const dest = document.getElementById('dest-drive-link').value.trim();
                            try {
                                const res = await fetch('/api/delete_result', {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify({
                                        title: video.title,
                                        channel: folder.name,
                                        dest: dest
                                    })
                                });
                                const resData = await res.json();
                                if (resData.success) {
                                    video.edited = false;
                                    cb.dataset.edited = 'false';
                                    itemEl.className = 'video-tree-item is-unedited';
                                    itemEl.querySelector('div:last-child').innerHTML = '<span class="badge-status unedited">⚪ Unedited</span>';
                                    fetchResults();
                                    selectedVideos.add(video.path);
                                    document.getElementById('preview-text-input').value = video.title;
                                    document.getElementById('canvas-banner-text').textContent = video.title.toUpperCase();
                                    updateSelectedCount();
                                    return;
                                }
                            } catch (err) {
                                alert('Lỗi khi xóa bản thành phẩm cũ: ' + err.message);
                            }
                        }
                        e.target.checked = false;
                        return;
                    }
                    selectedVideos.add(video.path);
                    document.getElementById('preview-text-input').value = video.title;
                    document.getElementById('canvas-banner-text').textContent = video.title.toUpperCase();
                } else {
                    selectedVideos.delete(video.path);
                }
                updateSelectedCount();
            });

            listEl.appendChild(itemEl);
        });

        // Folder collapse toggle
        folderEl.querySelector('.folder-header').addEventListener('click', (e) => {
            if (e.target.tagName === 'INPUT') return;
            listEl.classList.toggle('hidden');
            const icon = folderEl.querySelector('.folder-left i');
            icon.className = listEl.classList.contains('hidden') ? 'fa-solid fa-folder text-muted' : 'fa-solid fa-folder-open text-primary';
        });

        container.appendChild(folderEl);
    });
}

function updateExplorerStats(folders) {
    let totalVideos = 0;
    folders.forEach(f => totalVideos += f.videos.length);
    document.getElementById('selected-count-badge').textContent = selectedVideos.size;
}

function filterVideoTree(filter) {
    const items = document.querySelectorAll('.video-tree-item');
    items.forEach(item => {
        if (filter === 'all') item.style.display = 'flex';
        else if (filter === 'unedited') item.style.display = item.classList.contains('is-unedited') ? 'flex' : 'none';
        else if (filter === 'edited') item.style.display = item.classList.contains('is-edited') ? 'flex' : 'none';
    });
}

function updateSelectedCount() {
    document.getElementById('selected-count-badge').textContent = selectedVideos.size;
}

/* ==========================================================================
   5. Tab 1: Dashboard Analytics Calculations & Rendering
   ========================================================================== */
function updateDashboardSummary(folders) {
    let totalFolders = folders.length;
    let totalVideos = 0;
    let totalEdited = 0;

    folders.forEach(folder => {
        totalVideos += folder.videos.length;
        totalEdited += folder.videos.filter(v => v.edited).length;
    });

    let totalUnedited = totalVideos - totalEdited;
    let rate = totalVideos > 0 ? Math.round((totalEdited / totalVideos) * 100) : 0;

    // Update numbers
    document.getElementById('summary-total-folders').textContent = totalFolders;
    document.getElementById('summary-total-videos').textContent = totalVideos;
    document.getElementById('summary-edited-videos').textContent = totalEdited;
    document.getElementById('summary-unedited-videos').textContent = totalUnedited;
    
    // Update completion bar
    document.getElementById('summary-completion-rate').textContent = `${rate}%`;
    document.getElementById('summary-completion-bar').style.width = `${rate}%`;
}

function populateFolderFilterDropdown(folders) {
    const select = document.getElementById('select-folder-filter');
    select.innerHTML = '<option value="all">All Folders</option>';
    
    folders.forEach(f => {
        const opt = document.createElement('option');
        opt.value = f.name;
        opt.textContent = f.name;
        select.appendChild(opt);
    });
}

function renderDashboardTable(folders, selectedFilter) {
    const tbody = document.getElementById('dashboard-table-body');
    if (!folders || folders.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" class="table-empty">
                    <i class="fa-solid fa-folder-tree"></i> No directories scanned yet.
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = '';
    let counter = 1;

    folders.forEach(folder => {
        // Filter folder if not 'all'
        if (selectedFilter !== 'all' && folder.name !== selectedFilter) {
            return;
        }

        const total = folder.videos.length;
        const edited = folder.videos.filter(v => v.edited).length;
        const unedited = total - edited;
        const rate = total > 0 ? Math.round((edited / total) * 100) : 0;

        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td><strong>${counter++}</strong></td>
            <td>
                <span style="font-weight: 700; color: var(--text-primary);">
                    <i class="fa-solid fa-folder-open text-primary" style="margin-right: 6px;"></i> ${folder.name}
                </span>
            </td>
            <td style="text-align: center;">${total}</td>
            <td style="text-align: center;"><span class="badge badge-primary">${edited} video</span></td>
            <td style="text-align: center;"><span class="badge badge-info">${unedited} video</span></td>
            <td>
                <div class="table-progress-wrapper">
                    <div class="table-progress-bar-track">
                        <div class="table-progress-bar-fill" style="width: ${rate}%; background: ${rate === 100 ? 'var(--success)' : 'var(--primary)'}"></div>
                    </div>
                    <span class="table-progress-text">${rate}%</span>
                </div>
            </td>
            <td style="text-align: center;">
                <button class="btn btn-sm btn-secondary" onclick="actionStartEditFolder('${folder.name}')">
                    <i class="fa-solid fa-wand-magic-sparkles"></i> Edit
                </button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

function actionStartEditFolder(folderName) {
    // 1. Switch to Tab 2
    const studioTabBtn = document.querySelector('.tab-link[data-tab="tab-studio"]');
    if (studioTabBtn) studioTabBtn.click();

    // 2. Select/Expand only that folder in explorer tree
    const treeHeaders = document.querySelectorAll('.folder-header');
    treeHeaders.forEach(header => {
        const nameText = header.querySelector('.folder-left span').textContent.trim();
        const listEl = header.nextElementSibling;
        
        if (nameText === folderName) {
            listEl.classList.remove('hidden');
            // Check all unedited checkboxes inside this folder
            const checkboxes = listEl.querySelectorAll('.video-checkbox');
            checkboxes.forEach(cb => {
                const isEdited = cb.dataset.edited === 'true';
                if (!isEdited) {
                    cb.checked = true;
                    selectedVideos.add(cb.dataset.path);
                }
            });
        } else {
            // Uncheck other folders to keep clean focus
            listEl.classList.add('hidden');
            const checkboxes = listEl.querySelectorAll('.video-checkbox');
            checkboxes.forEach(cb => {
                cb.checked = false;
                selectedVideos.delete(cb.dataset.path);
            });
        }
    });

    updateSelectedCount();
}

// Attach action to window object so inline onclick functions can access it
window.actionStartEditFolder = actionStartEditFolder;

/* ==========================================================================
   6. Batch Processing & Realtime Progress Stream
   ========================================================================== */
async function startBatchProcessing() {
    const checkboxes = document.querySelectorAll('.video-checkbox:checked');
    if (checkboxes.length === 0) {
        alert("Please select at least 1 video to process!");
        return;
    }

    const videoItems = [];
    checkboxes.forEach(cb => {
        videoItems.push({
            path: cb.dataset.path,
            title: cb.dataset.title,
            channel: cb.dataset.channel
        });
    });

    const payload = {
        video_items: videoItems,
        video_paths: videoItems.map(item => item.path),
        dest_folder: document.getElementById('dest-drive-link').value.trim(),
        aspect_ratio: document.querySelector('input[name="aspect_ratio"]:checked').value,
        blur_bg: document.getElementById('effect-blur-bg').checked,
        hflip: document.getElementById('effect-hflip').checked,
        color_boost: document.getElementById('effect-color-boost').checked,
        banner_box_style: document.getElementById('banner-box-style').value,
        banner_font: document.getElementById('banner-font').value,
        banner_font_size: parseInt(document.getElementById('banner-font-size').value),
        banner_position: document.getElementById('banner-position').value,
        split_mode: document.getElementById('split-mode').value,
        export_full: document.getElementById('export-full-toggle').value === 'yes'
    };

    try {
        const res = await fetch('/api/start_batch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();

        if (data.status === 'started') {
            setProcessState(true);
            startPollingProgress();
        } else {
            alert("Render launch error: " + (data.error || "Unknown reason"));
        }
    } catch (err) {
        alert("API connection error: " + err.message);
    }
}

async function stopProcessing() {
    try {
        await fetch('/api/stop_batch', { method: 'POST' });
        setProcessState(false);
    } catch (err) {
        console.error(err);
    }
}

function setProcessState(running) {
    isRunning = running;
    const btnStart = document.getElementById('btn-start-processing');
    const btnStop = document.getElementById('btn-stop-processing');
    const statusDot = document.querySelector('.status-dot');
    const statusText = document.getElementById('status-text');

    if (running) {
        btnStart.classList.add('hidden');
        btnStop.classList.remove('hidden');
        statusDot.className = 'status-dot busy';
        statusText.textContent = 'Rendering videos...';
    } else {
        btnStart.classList.remove('hidden');
        btnStop.classList.add('hidden');
        statusDot.className = 'status-dot online';
        statusText.textContent = 'Ready';
        if (progressInterval) clearInterval(progressInterval);
    }
}

function startPollingProgress() {
    if (progressInterval) clearInterval(progressInterval);
    progressInterval = setInterval(async () => {
        try {
            const res = await fetch('/api/progress');
            const data = await res.json();

            // Progress Fill
            document.getElementById('progress-percentage').textContent = `${data.percentage || 0}%`;
            document.getElementById('progress-fill').style.width = `${data.percentage || 0}%`;
            document.getElementById('progress-current-task').textContent = data.current_task || "Rendering...";
            document.getElementById('render-status-text').textContent = data.is_running ? "Processing..." : "Completed";

            // Update Logs
            if (data.logs) {
                const term = document.getElementById('terminal-logs-window');
                term.innerHTML = data.logs.map(l => `<div class="log-line">${l}</div>`).join('');
                term.scrollTop = term.scrollHeight;
            }

            // Sync finish status
            if (!data.is_running && isRunning) {
                setProcessState(false);
                fetchResults();
                const source = document.getElementById('source-drive-link').value.trim();
                if (source) scanSourcePath(source); // Refresh Tree & Dashboard values
            }
        } catch (err) {
            console.error("Progress fetch error:", err);
        }
    }, 1200);
}

/* ==========================================================================
   7. Finished Outputs Tab & Video Management
   ========================================================================== */
function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function escapeAttr(str) {
    if (!str) return '';
    return String(str).replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/"/g, '&quot;');
}

async function fetchResults() {
    try {
        const dest = document.getElementById('dest-drive-link').value.trim();
        const res = await fetch(`/api/results?dest=${encodeURIComponent(dest)}`);
        const data = await res.json();

        const container = document.getElementById('finished-list-container');
        const badgeCount = document.getElementById('finished-total-badge');
        const results = data.results || [];
        
        if (badgeCount) {
            badgeCount.textContent = `${results.length} video${results.length === 1 ? '' : 's'}`;
        }

        if (results.length === 0) {
            container.innerHTML = `
                <div class="empty-finished-state">
                    <i class="fa-solid fa-clapperboard"></i>
                    <p>Chưa có video thành phẩm nào trong thư mục đích.</p>
                </div>
            `;
            return;
        }

        container.innerHTML = '';
        results.forEach(item => {
            const card = document.createElement('div');
            card.className = 'finished-card';

            // Tạo các nút part nhỏ để xem nhanh
            let partsHtml = '';
            if (item.parts && item.parts.length > 0) {
                partsHtml = `
                    <div class="finished-parts-chips">
                        ${item.parts.map((p, idx) => `
                            <button type="button" class="finished-part-chip" onclick="playFinishedVideo('${encodeURIComponent(p.url)}', '${escapeAttr(item.title)} - Part ${idx + 1}')" title="Xem trước ${escapeAttr(p.name)}">
                                <i class="fa-solid fa-play" style="font-size: 8px;"></i> Part ${idx + 1}
                            </button>
                        `).join('')}
                    </div>
                `;
            }

            card.innerHTML = `
                <div class="finished-info" style="flex: 1; min-width: 0;">
                    <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                        <span class="finished-title" style="font-size: 13px; font-weight: 700; color: var(--text-primary);" title="${escapeAttr(item.title)}">
                            <i class="fa-solid fa-circle-check text-success"></i> ${escapeHtml(item.title)}
                        </span>
                        <span class="badge" style="font-weight: 700; background: rgba(139, 92, 246, 0.12); color: var(--accent); border: 1px solid rgba(139, 92, 246, 0.2); padding: 2px 8px; border-radius: 4px; font-size: 11px;">
                            ${escapeHtml(item.folder_name)}
                        </span>
                    </div>
                    ${partsHtml}
                </div>
                <div class="finished-actions" style="display: flex; align-items: center; gap: 8px; flex-shrink: 0;">
                    <span style="font-size: 12px; color: var(--text-muted); font-weight: 700; margin-right: 4px;">
                        ${item.parts.length} videos
                    </span>
                    <button class="btn btn-sm btn-secondary" onclick="openOutputDirectory('${escapeAttr(item.path)}')" title="Mở thư mục chứa video trên máy">
                        <i class="fa-solid fa-folder-open"></i> Mở thư mục
                    </button>
                    <button class="btn btn-sm btn-danger" onclick="deleteFinishedVideo('${escapeAttr(item.path)}', '${escapeAttr(item.title)}', '${escapeAttr(item.folder_name)}')" title="Xóa video thành phẩm này">
                        <i class="fa-solid fa-trash-can"></i> Xóa
                    </button>
                </div>
            `;
            container.appendChild(card);
        });
    } catch (err) {
        console.error("Fetch results error:", err);
    }
}

async function deleteFinishedVideo(folderPath, videoTitle, channelName) {
    if (!confirm(`Bạn có chắc chắn muốn xóa video thành phẩm:\n"${videoTitle}"?\n\nThư mục thành phẩm và các video đã cắt sẽ bị xóa khỏi ổ đĩa.`)) {
        return;
    }
    
    // Đảm bảo dừng phát video và ngắt kết nối stream trước khi xóa
    const player = document.getElementById('modal-video-player');
    if (player) {
        player.pause();
        player.removeAttribute('src');
        player.load();
    }
    
    try {
        const dest = document.getElementById('dest-drive-link').value.trim();
        const res = await fetch('/api/delete_result', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                path: folderPath,
                title: videoTitle,
                channel: channelName,
                dest: dest
            })
        });
        const data = await res.json();
        
        if (data.success) {
            // Tải lại danh sách thành phẩm
            fetchResults();
            // Quét lại cây nguồn để video chuyển về trạng thái 'Unedited' ngay lập tức
            const source = document.getElementById('source-drive-link').value.trim();
            if (source) scanSourcePath(source);
        } else {
            alert("Lỗi khi xóa video: " + (data.errors ? data.errors.join(', ') : "Không xác định"));
        }
    } catch (err) {
        alert("Lỗi kết nối khi xóa: " + err.message);
    }
}

async function deleteAllFinishedVideos() {
    const dest = document.getElementById('dest-drive-link').value.trim();
    if (!confirm(`⚠️ CẢNH BÁO: Bạn có chắc chắn muốn xóa TOÀN BỘ video thành phẩm trong thư mục:\n${dest}?\n\nThao tác này không thể hoàn tác.`)) {
        return;
    }

    // Đảm bảo dừng phát video và ngắt kết nối stream trước khi xóa
    const player = document.getElementById('modal-video-player');
    if (player) {
        player.pause();
        player.removeAttribute('src');
        player.load();
    }

    try {
        const res = await fetch('/api/delete_all_results', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ dest: dest })
        });
        const data = await res.json();
        if (data.success) {
            fetchResults();
            const source = document.getElementById('source-drive-link').value.trim();
            if (source) scanSourcePath(source);
            alert("Đã xóa toàn bộ video thành phẩm thành công!");
        } else {
            alert("Lỗi khi xóa toàn bộ: " + (data.errors ? data.errors.join(', ') : "Không xác định"));
        }
    } catch (err) {
        alert("Lỗi kết nối: " + err.message);
    }
}

function playFinishedVideo(url, title) {
    const decodedUrl = decodeURIComponent(url);
    const modal = document.getElementById('video-modal');
    const player = document.getElementById('modal-video-player');
    const titleEl = document.getElementById('modal-video-title');
    
    titleEl.textContent = title || "Xem trước video thành phẩm";
    player.src = decodedUrl;
    modal.classList.remove('hidden');
    player.play().catch(() => {});
}

function openLocalFile(filePath) {
    fetch('/api/open_file', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: filePath })
    });
}

function openOutputDirectory(folderPath) {
    fetch('/api/open_folder', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: folderPath })
    });
}

// Bind methods to window for inline onclick handlers
window.openLocalFile = openLocalFile;
window.openOutputDirectory = openOutputDirectory;
window.deleteFinishedVideo = deleteFinishedVideo;
window.deleteAllFinishedVideos = deleteAllFinishedVideos;
window.playFinishedVideo = playFinishedVideo;
window.escapeHtml = escapeHtml;
window.escapeAttr = escapeAttr;

/* ==========================================================================
   5. Accounts & Channels Manager (New Sections)
   ========================================================================== */
let accountsData = { youtube_channels: [], tiktok_accounts: [] };
let editingChannelIdx = -1;
let editingAccountIdx = -1;

function initAccountsManager() {
    const btnToggleChannel = document.getElementById('btn-toggle-channel-form');
    const btnToggleAccount = document.getElementById('btn-toggle-account-form');
    const channelFormArea = document.getElementById('channel-form-area');
    const accountFormArea = document.getElementById('account-form-area');
    
    const btnCancelChannel = document.getElementById('btn-cancel-channel');
    const btnSaveChannel = document.getElementById('btn-save-channel');
    const btnCancelAccount = document.getElementById('btn-cancel-account');
    const btnSaveAccount = document.getElementById('btn-save-account');
    
    const btnToggleInputPw = document.getElementById('btn-toggle-input-pw');
    const inputAccPassword = document.getElementById('input-acc-password');
    const btnSavePaths = document.getElementById('btn-save-paths');
    
    // Save Paths configuration
    btnSavePaths.addEventListener('click', async (e) => {
        e.preventDefault();
        const source = document.getElementById('source-drive-link').value.trim();
        const dest = document.getElementById('dest-drive-link').value.trim();
        if (!source || !dest) {
            alert('Please input both source and destination paths!');
            return;
        }
        
        const isWebLink = (str) => str.startsWith('http://') || str.startsWith('https://') || str.includes('drive.google.com');
        if (isWebLink(source) || isWebLink(dest)) {
            alert('The system only accepts local directories (e.g. C:\\Users\\... or D:\\Output) for maximum speed and stability. Web links like Google Drive URLs are not supported!');
            return;
        }

        accountsData.source_path = source;
        accountsData.dest_path = dest;
        const success = await saveAccountsToBackend();
        if (success) {
            alert('Paths saved successfully!');
            scanSourcePath(source);
        }
    });
    
    // Toggle Channel Form
    btnToggleChannel.addEventListener('click', () => {
        editingChannelIdx = -1;
        clearChannelForm();
        channelFormArea.classList.toggle('hidden');
        btnToggleChannel.innerHTML = channelFormArea.classList.contains('hidden') 
            ? '<i class="fa-solid fa-plus"></i> Add New Channel'
            : '<i class="fa-solid fa-xmark"></i> Close Form';
    });
    
    btnCancelChannel.addEventListener('click', (e) => {
        e.preventDefault();
        channelFormArea.classList.add('hidden');
        btnToggleChannel.innerHTML = '<i class="fa-solid fa-plus"></i> Add New Channel';
        clearChannelForm();
    });
    
    // Toggle Account Form
    btnToggleAccount.addEventListener('click', () => {
        editingAccountIdx = -1;
        clearAccountForm();
        accountFormArea.classList.toggle('hidden');
        btnToggleAccount.innerHTML = accountFormArea.classList.contains('hidden')
            ? '<i class="fa-solid fa-plus"></i> Add New Account'
            : '<i class="fa-solid fa-xmark"></i> Close Form';
    });
    
    btnCancelAccount.addEventListener('click', (e) => {
        e.preventDefault();
        accountFormArea.classList.add('hidden');
        btnToggleAccount.innerHTML = '<i class="fa-solid fa-plus"></i> Add New Account';
        clearAccountForm();
    });
    
    // Eye icon inside Add Account form
    btnToggleInputPw.addEventListener('click', () => {
        if (inputAccPassword.type === 'password') {
            inputAccPassword.type = 'text';
            btnToggleInputPw.classList.remove('fa-eye-slash');
            btnToggleInputPw.classList.add('fa-eye');
        } else {
            inputAccPassword.type = 'password';
            btnToggleInputPw.classList.remove('fa-eye');
            btnToggleInputPw.classList.add('fa-eye-slash');
        }
    });
    
    // Auto-fill folder name when typing channel name
    const inputChanName = document.getElementById('input-channel-name');
    const inputChanFolder = document.getElementById('input-channel-folder');
    if (inputChanName && inputChanFolder) {
        inputChanName.addEventListener('input', (e) => {
            if (!inputChanFolder.value || inputChanFolder.dataset.autofilled === 'true') {
                inputChanFolder.value = e.target.value;
                inputChanFolder.dataset.autofilled = 'true';
            }
        });
        inputChanFolder.addEventListener('input', () => {
            inputChanFolder.dataset.autofilled = 'false';
        });
    }
    
    // Save Channel
    btnSaveChannel.addEventListener('click', async (e) => {
        e.preventDefault();
        const name = document.getElementById('input-channel-name').value.trim();
        const url = document.getElementById('input-channel-url').value.trim();
        let folder = document.getElementById('input-channel-folder').value.trim();
        if (!folder && name) {
            folder = name;
        }
        
        if (!name || !folder) {
            alert('Please enter both the Channel Name and Source Folder Name!');
            return;
        }
        
        const newChan = { name, url, folder_name: folder, note: 'Custom configured' };
        
        if (editingChannelIdx > -1) {
            // Keep existing downloaded count if editing
            const oldChan = accountsData.youtube_channels[editingChannelIdx];
            newChan.total_downloaded = oldChan.total_downloaded || 0;
            accountsData.youtube_channels[editingChannelIdx] = newChan;
        } else {
            newChan.total_downloaded = 0;
            accountsData.youtube_channels.push(newChan);
        }
        
        const success = await saveAccountsToBackend();
        if (success) {
            channelFormArea.classList.add('hidden');
            btnToggleChannel.innerHTML = '<i class="fa-solid fa-plus"></i> Add New Channel';
            clearChannelForm();
            await fetchAccountsData();
            
            // Tự động quét lại Source & Output để hiển thị ngay folder mới
            const src = document.getElementById('source-drive-link').value.trim();
            if (src) scanSourcePath(src);
            fetchResults();
            fetchPublishingMatrix();
        }
    });
    
    // Save Account
    btnSaveAccount.addEventListener('click', async (e) => {
        e.preventDefault();
        const username = document.getElementById('input-acc-username').value.trim();
        const password = document.getElementById('input-acc-password').value.trim();
        const email = document.getElementById('input-acc-email').value.trim();
        const emailConfirm = document.getElementById('input-acc-email-confirm').value.trim();
        const ipOrig = document.getElementById('input-acc-ip-orig').value.trim();
        const ipBuild = document.getElementById('input-acc-ip-build').value.trim();
        const date = document.getElementById('input-acc-date').value;
        const target = document.getElementById('input-acc-target').value;
        const hashtags = document.getElementById('input-acc-hashtags').value.trim();
        const content = document.getElementById('input-acc-content').value.trim();
        const note = document.getElementById('input-acc-note').value.trim();
        
        if (!username || !password) {
            alert('Please enter both Account Name and Password!');
            return;
        }
        
        const newAcc = {
            account_name: username,
            password: password,
            mail: email,
            mail_confirm: emailConfirm,
            original_ip: ipOrig,
            build_up_ip: ipBuild,
            created_date: date,
            target_channel: target,
            content: content,
            hashtag: hashtags,
            note: note
        };
        
        if (editingAccountIdx > -1) {
            accountsData.tiktok_accounts[editingAccountIdx] = newAcc;
        } else {
            accountsData.tiktok_accounts.push(newAcc);
        }
        
        const success = await saveAccountsToBackend();
        if (success) {
            accountFormArea.classList.add('hidden');
            btnToggleAccount.innerHTML = '<i class="fa-solid fa-plus"></i> Add New Account';
            clearAccountForm();
            await fetchAccountsData();
        }
    });
    
    fetchAccountsData();
}

function clearChannelForm() {
    document.getElementById('input-channel-name').value = '';
    document.getElementById('input-channel-url').value = '';
    document.getElementById('input-channel-folder').value = '';
}

function clearAccountForm() {
    document.getElementById('input-acc-username').value = '';
    document.getElementById('input-acc-password').value = '';
    document.getElementById('input-acc-email').value = '';
    document.getElementById('input-acc-email-confirm').value = '';
    document.getElementById('input-acc-ip-orig').value = '';
    document.getElementById('input-acc-ip-build').value = '';
    document.getElementById('input-acc-date').value = '';
    document.getElementById('input-acc-target').value = '';
    document.getElementById('input-acc-hashtags').value = '';
    document.getElementById('input-acc-content').value = '';
    document.getElementById('input-acc-note').value = '';
}

async function fetchAccountsData() {
    const sourcePathInput = document.getElementById('source-drive-link');
    const destPathInput = document.getElementById('dest-drive-link');
    const currentSource = sourcePathInput.value.trim();
    
    try {
        const res = await fetch(`/api/accounts?source=${encodeURIComponent(currentSource)}`);
        const data = await res.json();
        accountsData = data || { youtube_channels: [], tiktok_accounts: [] };
        
        let shouldScan = false;
        if (data.source_path && !currentSource) {
            sourcePathInput.value = data.source_path;
            shouldScan = true;
        }
        if (data.dest_path && !destPathInput.value.trim()) {
            destPathInput.value = data.dest_path;
        }
        
        renderChannelsTable();
        renderAccountsTable();
        updateTargetChannelDropdown();
        
        if (shouldScan) {
            scanSourcePath(data.source_path);
        }
    } catch (err) {
        console.error('Error fetching accounts:', err);
    }
}

async function saveAccountsToBackend() {
    try {
        const res = await fetch('/api/accounts/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(accountsData)
        });
        const result = await res.json();
        return result.status === 'saved';
    } catch (err) {
        console.error('Error saving accounts to backend:', err);
        alert('Connection error when saving account!');
        return false;
    }
}

function renderChannelsTable() {
    const tbody = document.getElementById('channels-table-body');
    tbody.innerHTML = '';
    
    const channels = accountsData.youtube_channels || [];
    if (channels.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6" class="table-empty">No YouTube channels configured.</td>
            </tr>
        `;
        return;
    }
    
    channels.forEach((chan, idx) => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${idx + 1}</td>
            <td><strong>${chan.name}</strong></td>
            <td>
                ${chan.url ? `<a href="${chan.url}" target="_blank" class="text-primary" style="text-decoration: none;"><i class="fa-solid fa-arrow-up-right-from-square"></i> View Channel</a>` : '<span class="text-muted">No URL</span>'}
            </td>
            <td><code>${chan.folder_name}</code></td>
            <td style="text-align: center;">
                <span class="badge" style="background: var(--primary); font-weight: 700; padding: 4px 8px; border-radius: var(--radius-sm);">${chan.total_downloaded || 0} clips</span>
            </td>
            <td style="text-align: center;">
                <button class="btn btn-outline btn-xs btn-edit-chan" data-index="${idx}" style="padding: 4px 8px; font-size: 11px; margin-right: 4px;"><i class="fa-solid fa-pen"></i></button>
                <button class="btn btn-danger btn-xs btn-delete-chan" data-index="${idx}" style="padding: 4px 8px; font-size: 11px; background: var(--danger);"><i class="fa-solid fa-trash"></i></button>
            </td>
        `;
        
        tr.querySelector('.btn-edit-chan').addEventListener('click', () => {
            editChannel(idx);
        });
        
        tr.querySelector('.btn-delete-chan').addEventListener('click', () => {
            if (confirm(`Are you sure you want to delete channel ${chan.name}?`)) {
                deleteChannel(idx);
            }
        });
        
        tbody.appendChild(tr);
    });
}

function renderAccountsTable() {
    const tbody = document.getElementById('accounts-table-body');
    tbody.innerHTML = '';
    
    const accounts = accountsData.tiktok_accounts || [];
    if (accounts.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="9" class="table-empty">No TikTok accounts configured.</td>
            </tr>
        `;
        return;
    }
    
    accounts.forEach((acc, idx) => {
        const tr = document.createElement('tr');
        
        const mailDisplay = acc.mail 
            ? `<div>${acc.mail}</div>${acc.mail_confirm ? `<div style="font-size: 11px; opacity:0.6;"><i class="fa-solid fa-reply"></i> ${acc.mail_confirm}</div>` : ''}` 
            : '<span class="text-muted">-</span>';
            
        const ipDisplay = `
            <div><span class="badge-ip" title="Original IP"><i class="fa-solid fa-house"></i> ${acc.original_ip || 'No IP'}</span></div>
            <div><span class="badge-ip" title="Nurtured IP"><i class="fa-solid fa-network-wired"></i> ${acc.build_up_ip || 'No IP'}</span></div>
        `;
        
        const matchingChan = (accountsData.youtube_channels || []).find(c => c.name === acc.target_channel);
        const chanUrl = matchingChan ? matchingChan.url : '';
        const targetChannelDisplay = chanUrl
            ? `<a href="${chanUrl}" target="_blank" class="badge" style="background: rgba(139, 92, 246, 0.1); color: var(--accent); border: 1px solid rgba(139, 92, 246, 0.2); padding: 4.5px 8px; text-decoration: none; display: inline-flex; align-items: center; gap: 4px; cursor: pointer; font-weight: 700; border-radius: 4px;" title="Open YouTube channel"><i class="fa-brands fa-youtube" style="color: #ef4444;"></i> ${acc.target_channel}</a>`
            : `<span class="badge" style="background: rgba(255,255,255,0.05); border: 1px solid var(--border-color); padding: 4.5px 8px; border-radius: 4px;">${acc.target_channel || '-'}</span>`;

        tr.innerHTML = `
            <td>${idx + 1}</td>
            <td>
                <div style="font-weight: 700;">@${acc.account_name}</div>
                ${acc.content ? `<div style="font-size:11px; color:var(--text-secondary);"><i class="fa-solid fa-tags"></i> ${acc.content}</div>` : ''}
            </td>
            <td>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <input type="password" class="table-pw-input" value="${acc.password}" disabled style="background:transparent; border:none; color:inherit; font-family:monospace; font-size:14px; width:100px; padding:0;">
                    <i class="fa-solid fa-eye-slash btn-toggle-table-pw" style="cursor: pointer; opacity: 0.6; font-size: 13px;"></i>
                </div>
            </td>
            <td>${mailDisplay}</td>
            <td>${ipDisplay}</td>
            <td>${targetChannelDisplay}</td>
            <td><span style="font-size: 11px; white-space:nowrap;">${acc.created_date || '-'}</span></td>
            <td>
                ${acc.hashtag ? `<div style="font-size:11px; color:var(--primary); font-family:monospace; max-width: 150px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${acc.hashtag}">${acc.hashtag}</div>` : ''}
                ${acc.note ? `<div style="font-size:11px; opacity:0.7; max-width: 150px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${acc.note}">${acc.note}</div>` : ''}
            </td>
            <td style="text-align: center;">
                <button class="btn btn-outline btn-xs btn-edit-acc" data-index="${idx}" style="padding: 4px 8px; font-size: 11px; margin-right: 4px;"><i class="fa-solid fa-pen"></i></button>
                <button class="btn btn-danger btn-xs btn-delete-acc" data-index="${idx}" style="padding: 4px 8px; font-size: 11px; background: var(--danger);"><i class="fa-solid fa-trash"></i></button>
            </td>
        `;
        
        const toggleIcon = tr.querySelector('.btn-toggle-table-pw');
        const pwInput = tr.querySelector('.table-pw-input');
        toggleIcon.addEventListener('click', () => {
            if (pwInput.type === 'password') {
                pwInput.type = 'text';
                toggleIcon.classList.remove('fa-eye-slash');
                toggleIcon.classList.add('fa-eye');
            } else {
                pwInput.type = 'password';
                toggleIcon.classList.remove('fa-eye');
                toggleIcon.classList.add('fa-eye-slash');
            }
        });
        
        tr.querySelector('.btn-edit-acc').addEventListener('click', () => {
            editAccount(idx);
        });
        
        tr.querySelector('.btn-delete-acc').addEventListener('click', () => {
            if (confirm(`Are you sure you want to delete account @${acc.account_name}?`)) {
                deleteAccount(idx);
            }
        });
        
        tbody.appendChild(tr);
    });
}

function updateTargetChannelDropdown() {
    const select = document.getElementById('input-acc-target');
    select.innerHTML = '<option value="">Select YouTube channel...</option>';
    
    const channels = accountsData.youtube_channels || [];
    channels.forEach(chan => {
        const opt = document.createElement('option');
        opt.value = chan.name;
        opt.textContent = chan.name;
        select.appendChild(opt);
    });
}

function editChannel(idx) {
    const chan = accountsData.youtube_channels[idx];
    editingChannelIdx = idx;
    
    document.getElementById('input-channel-name').value = chan.name;
    document.getElementById('input-channel-url').value = chan.url || '';
    document.getElementById('input-channel-folder').value = chan.folder_name;
    
    const formArea = document.getElementById('channel-form-area');
    formArea.classList.remove('hidden');
    document.getElementById('btn-toggle-channel-form').innerHTML = '<i class="fa-solid fa-xmark"></i> Close Form';
    formArea.scrollIntoView({ behavior: 'smooth' });
}

async function deleteChannel(idx) {
    accountsData.youtube_channels.splice(idx, 1);
    const success = await saveAccountsToBackend();
    if (success) {
        await fetchAccountsData();
    }
}

function editAccount(idx) {
    const acc = accountsData.tiktok_accounts[idx];
    editingAccountIdx = idx;
    
    document.getElementById('input-acc-username').value = acc.account_name;
    document.getElementById('input-acc-password').value = acc.password;
    document.getElementById('input-acc-email').value = acc.mail || '';
    document.getElementById('input-acc-email-confirm').value = acc.mail_confirm || '';
    document.getElementById('input-acc-ip-orig').value = acc.original_ip || '';
    document.getElementById('input-acc-ip-build').value = acc.build_up_ip || '';
    document.getElementById('input-acc-date').value = acc.created_date || '';
    document.getElementById('input-acc-target').value = acc.target_channel || '';
    document.getElementById('input-acc-hashtags').value = acc.hashtag || '';
    document.getElementById('input-acc-content').value = acc.content || '';
    document.getElementById('input-acc-note').value = acc.note || '';
    
    const formArea = document.getElementById('account-form-area');
    formArea.classList.remove('hidden');
    document.getElementById('btn-toggle-account-form').innerHTML = '<i class="fa-solid fa-xmark"></i> Close Form';
    formArea.scrollIntoView({ behavior: 'smooth' });
}

async function deleteAccount(idx) {
    accountsData.tiktok_accounts.splice(idx, 1);
    const success = await saveAccountsToBackend();
    if (success) {
        await fetchAccountsData();
        if (typeof fetchPublishingMatrix === 'function') {
            fetchPublishingMatrix();
        }
    }
}

/* ==========================================================================
   10. Section: TikTok Publishing & Target Channels Tracker
   ========================================================================== */
let publishingMatrixData = { accounts: [], youtube_channels: [] };
let activePublishingAccountName = null;
let activePublishingFilter = 'all'; // 'all', 'pending', 'posted'
let activePublishingChannelFilter = 'all';
let publishingSearchQuery = '';

function initPublishingTracker() {
    const searchInput = document.getElementById('search-pub-account');
    const filterBtns = document.querySelectorAll('.pub-filter-btn');
    const channelFilterSelect = document.getElementById('pub-filter-channel');
    const btnChangeTarget = document.getElementById('btn-pub-change-target');
    const btnCopyHashtags = document.getElementById('btn-pub-copy-hashtags');
    const btnMarkAll = document.getElementById('btn-pub-mark-all');
    const btnRefreshPub = document.getElementById('btn-refresh-publishing');

    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            publishingSearchQuery = e.target.value.toLowerCase().trim();
            renderPublishingAccountsList();
        });
    }

    filterBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            filterBtns.forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            activePublishingFilter = e.target.dataset.filter;
            renderPublishingClipsFeed();
        });
    });

    if (channelFilterSelect) {
        channelFilterSelect.addEventListener('change', (e) => {
            activePublishingChannelFilter = e.target.value;
            renderPublishingClipsFeed();
        });
    }

    if (btnChangeTarget) {
        btnChangeTarget.addEventListener('click', handleSwitchTargetChannel);
    }

    if (btnCopyHashtags) {
        btnCopyHashtags.addEventListener('click', handleCopyAccountHashtags);
    }

    if (btnMarkAll) {
        btnMarkAll.addEventListener('click', handleBatchMarkAllPosted);
    }

    if (btnRefreshPub) {
        btnRefreshPub.addEventListener('click', () => {
            fetchPublishingMatrix();
        });
    }

    fetchPublishingMatrix(true);
}

async function fetchPublishingMatrix(silent = false) {
    try {
        const dest = document.getElementById('dest-drive-link')?.value.trim() || '';
        const res = await fetch(`/api/publishing_matrix?dest=${encodeURIComponent(dest)}`);
        const data = await res.json();
        
        publishingMatrixData = data;
        
        // Cập nhật số lượng tài khoản trên badge
        const countBadge = document.getElementById('pub-accounts-count');
        if (countBadge) {
            countBadge.textContent = `${data.accounts?.length || 0} accounts`;
        }

        renderPublishingAccountsList();
        
        // Nếu đã có tài khoản đang chọn, giữ nguyên hoặc chọn tài khoản đầu tiên
        if (!activePublishingAccountName && data.accounts && data.accounts.length > 0) {
            selectPublishingAccount(data.accounts[0].account_name);
        } else if (activePublishingAccountName) {
            const exists = data.accounts?.some(a => a.account_name === activePublishingAccountName);
            if (exists) {
                selectPublishingAccount(activePublishingAccountName);
            } else if (data.accounts && data.accounts.length > 0) {
                selectPublishingAccount(data.accounts[0].account_name);
            }
        }
    } catch (err) {
        console.error("Fetch publishing matrix error:", err);
    }
}

function renderPublishingAccountsList() {
    const listContainer = document.getElementById('pub-accounts-list');
    if (!listContainer) return;

    const accounts = publishingMatrixData.accounts || [];
    const filteredAccounts = accounts.filter(acc => {
        if (!publishingSearchQuery) return true;
        return acc.account_name.toLowerCase().includes(publishingSearchQuery) ||
               (acc.target_channel && acc.target_channel.toLowerCase().includes(publishingSearchQuery)) ||
               (acc.mail && acc.mail.toLowerCase().includes(publishingSearchQuery));
    });

    if (filteredAccounts.length === 0) {
        listContainer.innerHTML = `
            <div class="empty-state" style="padding: 20px;">
                <i class="fa-solid fa-users-slash"></i>
                <p>No matching TikTok accounts.</p>
            </div>
        `;
        return;
    }

    listContainer.innerHTML = '';
    filteredAccounts.forEach(acc => {
        const item = document.createElement('div');
        const isActive = acc.account_name === activePublishingAccountName;
        item.className = `pub-acc-item ${isActive ? 'active' : ''}`;
        
        const stats = acc.stats || { total: 0, posted: 0, completion_rate: 0 };
        const targetLabel = acc.target_channel ? acc.target_channel : 'No Target';

        item.innerHTML = `
            <div class="pub-acc-item-top">
                <span class="pub-acc-item-name">
                    <i class="fa-brands fa-tiktok text-accent"></i> ${escapeHtml(acc.account_name)}
                </span>
                <span class="badge" style="font-size: 10px; font-weight: 700; background: rgba(59, 130, 246, 0.12); color: var(--primary); border: 1px solid rgba(59, 130, 246, 0.2);">
                    🎯 ${escapeHtml(targetLabel)}
                </span>
            </div>
            <div class="pub-acc-item-meta">
                <span>Posted: <strong style="color: var(--success);">${stats.posted}</strong> / ${stats.total} clips</span>
                <span style="font-weight: 700;">${stats.completion_rate}%</span>
            </div>
            <div class="pub-acc-mini-bar">
                <div class="pub-acc-mini-fill" style="width: ${stats.completion_rate}%;"></div>
            </div>
        `;

        item.addEventListener('click', () => {
            selectPublishingAccount(acc.account_name);
        });

        listContainer.appendChild(item);
    });
}

function selectPublishingAccount(accountName) {
    activePublishingAccountName = accountName;
    
    const accounts = publishingMatrixData.accounts || [];
    const acc = accounts.find(a => a.account_name === accountName);
    
    // Highlight active in list
    document.querySelectorAll('.pub-acc-item').forEach(el => el.classList.remove('active'));
    renderPublishingAccountsList();

    if (!acc) return;

    // Update Header Card Info
    document.getElementById('pub-acc-name').textContent = acc.account_name;
    document.getElementById('pub-acc-ip-badge').textContent = `IP: ${acc.build_up_ip || acc.original_ip || 'Default'}`;
    document.getElementById('pub-acc-mail').innerHTML = `<i class="fa-solid fa-envelope"></i> ${escapeHtml(acc.mail || 'No email')}`;
    document.getElementById('pub-acc-hashtag').innerHTML = `<i class="fa-solid fa-hashtag"></i> ${escapeHtml(acc.hashtag || 'No hashtags configured')}`;

    // Populate Target Channel Select Dropdown
    const selectTarget = document.getElementById('pub-select-target');
    if (selectTarget) {
        selectTarget.innerHTML = '';
        
        // Danh sách kênh từ youtube_channels
        const channels = publishingMatrixData.youtube_channels || [];
        
        // Thêm option rỗng nếu chưa có
        if (!acc.target_channel) {
            const optNone = document.createElement('option');
            optNone.value = '';
            optNone.textContent = '-- Chọn kênh mục tiêu --';
            selectTarget.appendChild(optNone);
        }

        channels.forEach(ch => {
            const opt = document.createElement('option');
            opt.value = ch.name;
            opt.textContent = ch.name;
            if (ch.name === acc.target_channel) {
                opt.selected = true;
            }
            selectTarget.appendChild(opt);
        });

        // Nếu kênh hiện tại của acc chưa có trong danh sách channels, vẫn thêm vào
        if (acc.target_channel && !channels.some(c => c.name === acc.target_channel)) {
            const optCurrent = document.createElement('option');
            optCurrent.value = acc.target_channel;
            optCurrent.textContent = `${acc.target_channel} (Tùy chỉnh)`;
            optCurrent.selected = true;
            selectTarget.appendChild(optCurrent);
        }
    }

    // Render Clips Feed for this account
    renderPublishingClipsFeed();
}

function renderPublishingClipsFeed() {
    const container = document.getElementById('pub-clips-container');
    if (!container) return;

    const accounts = publishingMatrixData.accounts || [];
    const acc = accounts.find(a => a.account_name === activePublishingAccountName);

    if (!acc) {
        container.innerHTML = `
            <div class="empty-state">
                <i class="fa-solid fa-clapperboard"></i>
                <p>Vui lòng chọn một tài khoản TikTok để theo dõi clip.</p>
            </div>
        `;
        return;
    }

    const clips = acc.clips || [];
    
    // Update Channel Filter Dropdown options
    const channelFilterSelect = document.getElementById('pub-filter-channel');
    if (channelFilterSelect) {
        const uniqueChannels = Array.from(new Set(clips.map(c => c.channel).filter(Boolean)));
        const currentSelectedVal = channelFilterSelect.value;
        
        channelFilterSelect.innerHTML = '<option value="all">Tất cả nguồn kênh</option>';
        uniqueChannels.forEach(ch => {
            const opt = document.createElement('option');
            opt.value = ch;
            opt.textContent = `Kênh: ${ch}`;
            if (ch === currentSelectedVal) opt.selected = true;
            channelFilterSelect.appendChild(opt);
        });
    }

    // Filter clips
    const filteredClips = clips.filter(c => {
        if (activePublishingFilter === 'pending' && c.posted) return false;
        if (activePublishingFilter === 'posted' && !c.posted) return false;
        if (activePublishingChannelFilter !== 'all' && c.channel !== activePublishingChannelFilter) return false;
        return true;
    });

    // Update Counter Badges in Toolbar
    const allCount = clips.length;
    const pendingCount = clips.filter(c => !c.posted).length;
    const postedCount = clips.filter(c => c.posted).length;

    document.getElementById('pub-count-all').textContent = allCount;
    document.getElementById('pub-count-pending').textContent = pendingCount;
    document.getElementById('pub-count-posted').textContent = postedCount;

    if (filteredClips.length === 0) {
        container.innerHTML = `
            <div class="empty-state" style="padding: 40px;">
                <i class="fa-solid fa-film"></i>
                <p>${clips.length === 0 ? `Chưa có video thành phẩm nào cho kênh mục tiêu: <strong>${escapeHtml(acc.target_channel || 'Chưa gán')}</strong>.` : 'Không có clip nào phù hợp với bộ lọc hiện tại.'}</p>
                ${clips.length === 0 ? `<p style="font-size: 11px; color: var(--text-muted); margin-top: 6px;">Hãy render video của kênh <strong>${escapeHtml(acc.target_channel)}</strong> tại tab Editor Studio để video xuất hiện tại đây!</p>` : ''}
            </div>
        `;
        return;
    }

    container.innerHTML = '';
    filteredClips.forEach(clip => {
        const row = document.createElement('div');
        row.className = `pub-clip-row ${clip.posted ? 'is-posted' : ''}`;

        // Badge nguồn kênh: Hiện rõ kênh hiện tại vs kênh cũ đã đăng
        let sourceBadgeHtml = '';
        if (clip.is_current_target) {
            sourceBadgeHtml = `<span class="pub-source-badge pub-source-current" title="Kênh mục tiêu hiện tại"><i class="fa-solid fa-bullseye"></i> ${escapeHtml(clip.channel)}</span>`;
        } else {
            sourceBadgeHtml = `<span class="pub-source-badge pub-source-history" title="Kênh trước đây đã lưu lịch sử"><i class="fa-solid fa-clock-rotate-left"></i> ${escapeHtml(clip.channel)} (Kênh cũ)</span>`;
        }

        // Parts buttons
        let partsHtml = '';
        if (clip.parts && clip.parts.length > 0) {
            partsHtml = `
                <div class="finished-parts-chips" style="margin-top: 4px;">
                    ${clip.parts.map((p, idx) => `
                        <button type="button" class="finished-part-chip" onclick="playFinishedVideo('${encodeURIComponent(p.url)}', '${escapeAttr(clip.title)} - Part ${idx + 1}')" title="Xem trước ${escapeAttr(p.name)}">
                            <i class="fa-solid fa-play" style="font-size: 8px;"></i> Part ${idx + 1}
                        </button>
                    `).join('')}
                </div>
            `;
        }

        const postedTagHtml = clip.posted 
            ? `<span class="pub-posted-tag"><i class="fa-solid fa-circle-check"></i> Đã đăng ${clip.posted_at ? `(${clip.posted_at})` : ''}</span>`
            : '';

        row.innerHTML = `
            <div class="pub-clip-left">
                <button type="button" class="pub-clip-checkbox-btn" title="${clip.posted ? 'Bấm để đánh dấu Chưa Đăng' : 'Bấm để đánh dấu ĐÃ ĐĂNG'}" onclick="handleToggleClipPost('${escapeAttr(clip.key)}', '${escapeAttr(clip.channel)}', '${escapeAttr(clip.title)}', ${!clip.posted})">
                    <i class="fa-solid fa-check"></i>
                </button>
                <div class="pub-clip-info">
                    <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                        <span class="pub-clip-title" title="${escapeAttr(clip.title)}">${escapeHtml(clip.title)}</span>
                        ${sourceBadgeHtml}
                        ${postedTagHtml}
                    </div>
                    ${partsHtml}
                </div>
            </div>

            <div class="pub-clip-actions">
                <button class="btn btn-sm btn-secondary" onclick="handleCopyCaptionForClip('${escapeAttr(clip.title)}')" title="Sao chép Tiêu đề clip + Hashtag tài khoản">
                    <i class="fa-regular fa-copy"></i> Copy Caption
                </button>
                ${clip.path ? `
                    <button class="btn btn-sm btn-outline" onclick="openOutputDirectory('${escapeAttr(clip.path)}')" title="Mở thư mục chứa file">
                        <i class="fa-solid fa-folder-open"></i>
                    </button>
                ` : ''}
            </div>
        `;

        container.appendChild(row);
    });
}

async function handleToggleClipPost(clipKey, channel, title, newPosted) {
    if (!activePublishingAccountName) return;

    try {
        const res = await fetch('/api/publishing/toggle_post', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                account_name: activePublishingAccountName,
                clip_key: clipKey,
                channel: channel,
                title: title,
                posted: newPosted
            })
        });

        const data = await res.json();
        if (data.success) {
            // Cập nhật trạng thái cục bộ ngay lập tức
            const accounts = publishingMatrixData.accounts || [];
            const acc = accounts.find(a => a.account_name === activePublishingAccountName);
            if (acc) {
                let clip = acc.clips?.find(c => c.key === clipKey);
                if (clip) {
                    clip.posted = newPosted;
                    clip.posted_at = data.posted_at || '';
                }
                
                // Cập nhật lại stats
                const total = acc.clips.length;
                const postedCount = acc.clips.filter(c => c.posted).length;
                acc.stats = {
                    total: total,
                    posted: postedCount,
                    pending: total - postedCount,
                    completion_rate: total > 0 ? Math.round(postedCount / total * 100) : 0
                };
            }
            
            renderPublishingAccountsList();
            renderPublishingClipsFeed();
        } else {
            alert('Lỗi cập nhật trạng thái: ' + (data.error || 'Unknown'));
        }
    } catch (err) {
        alert('Lỗi kết nối: ' + err.message);
    }
}

async function handleSwitchTargetChannel() {
    if (!activePublishingAccountName) return;

    const selectTarget = document.getElementById('pub-select-target');
    const newTarget = selectTarget.value.trim();
    if (!newTarget) {
        alert('Vui lòng chọn một kênh YouTube mục tiêu!');
        return;
    }

    const accounts = publishingMatrixData.accounts || [];
    const acc = accounts.find(a => a.account_name === activePublishingAccountName);
    const oldTarget = acc?.target_channel || '';

    if (newTarget === oldTarget) {
        alert(`Tài khoản "${activePublishingAccountName}" đã và đang sử dụng kênh mục tiêu "${newTarget}" rồi!`);
        return;
    }

    const confirmMsg = `Bạn có chắc chắn muốn chuyển kênh mục tiêu của tài khoản "${activePublishingAccountName}" từ "${oldTarget || 'Chưa có'}" sang "${newTarget}" không?\n\n- Các clip đã đăng từ kênh "${oldTarget}" vẫn sẽ được lưu lại trong lịch sử.\n- Toàn bộ video thành phẩm của kênh mới "${newTarget}" sẽ được tự động nạp vào danh sách.`;
    if (!confirm(confirmMsg)) return;

    try {
        const res = await fetch('/api/publishing/change_target', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                account_name: activePublishingAccountName,
                new_target_channel: newTarget
            })
        });

        const data = await res.json();
        if (data.success) {
            await fetchPublishingMatrix();
            // Đồng bộ sang accounts.json của Tab Accounts Manager nếu có
            if (typeof fetchAccountsData === 'function') {
                fetchAccountsData();
            }
            alert(`Đã chuyển kênh mục tiêu sang "${newTarget}" thành công!`);
        } else {
            alert('Lỗi chuyển đổi kênh: ' + (data.error || 'Unknown'));
        }
    } catch (err) {
        alert('Lỗi kết nối: ' + err.message);
    }
}

function handleCopyAccountHashtags() {
    if (!activePublishingAccountName) return;
    const accounts = publishingMatrixData.accounts || [];
    const acc = accounts.find(a => a.account_name === activePublishingAccountName);
    if (!acc || !acc.hashtag) {
        alert('Tài khoản này chưa có cấu hình Hashtag!');
        return;
    }

    navigator.clipboard.writeText(acc.hashtag).then(() => {
        alert(`Đã sao chép Hashtag của tài khoản "${activePublishingAccountName}" vào Clipboard!`);
    });
}

function handleCopyCaptionForClip(clipTitle) {
    if (!activePublishingAccountName) return;
    const accounts = publishingMatrixData.accounts || [];
    const acc = accounts.find(a => a.account_name === activePublishingAccountName);
    const hashtag = acc?.hashtag || '';
    const fullCaption = `${clipTitle}\n\n${hashtag}`.trim();

    navigator.clipboard.writeText(fullCaption).then(() => {
        alert(`Đã sao chép Caption + Hashtag của clip:\n"${clipTitle}" vào Clipboard!`);
    });
}

async function handleBatchMarkAllPosted() {
    if (!activePublishingAccountName) return;
    const accounts = publishingMatrixData.accounts || [];
    const acc = accounts.find(a => a.account_name === activePublishingAccountName);
    if (!acc) return;

    const pendingClips = acc.clips?.filter(c => !c.posted) || [];
    if (pendingClips.length === 0) {
        alert('Tất cả clip hiện tại đã được đánh dấu Đã Đăng rồi!');
        return;
    }

    if (!confirm(`Bạn có chắc chắn muốn đánh dấu ĐÃ ĐĂNG cho tất cả ${pendingClips.length} clips chưa đăng của tài khoản "${activePublishingAccountName}" không?`)) {
        return;
    }

    try {
        const res = await fetch('/api/publishing/batch_toggle', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                account_name: activePublishingAccountName,
                clip_keys: pendingClips.map(c => c.key),
                posted: true
            })
        });

        const data = await res.json();
        if (data.success) {
            await fetchPublishingMatrix();
            alert(`Đã đánh dấu Đã Đăng cho ${pendingClips.length} clips thành công!`);
        } else {
            alert('Lỗi cập nhật: ' + (data.error || 'Unknown'));
        }
    } catch (err) {
        alert('Lỗi kết nối: ' + err.message);
    }
}

// Bind to window for inline onclick access
window.initPublishingTracker = initPublishingTracker;
window.fetchPublishingMatrix = fetchPublishingMatrix;
window.selectPublishingAccount = selectPublishingAccount;
window.handleToggleClipPost = handleToggleClipPost;
window.handleCopyCaptionForClip = handleCopyCaptionForClip;
