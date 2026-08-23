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
    initSettingsManager();
    initAccountsManager();
    initPublishingTracker();
    initAutoPilotHub();
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
            if (targetTab === 'tab-autopilot') {
                loadAutopilotQueue();
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
        let dest = document.getElementById('dest-drive-link')?.value?.trim();
        if (!dest) {
            dest = accountsData.dest_path || 'D:/Antigravity/tiktok_running/output_product';
        }
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

    if (btnOpenDest) btnOpenDest.addEventListener('click', openDestFolderAction);
    if (linkOpenGDriveTab) {
        linkOpenGDriveTab.addEventListener('click', (e) => {
            e.preventDefault();
            openDestFolderAction();
        });
    }

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

    initExplorerControls();
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

let currentVideoTreeFilter = 'all';
let currentVideoTreeSearch = '';

function renderVideoTree(folders) {
    const container = document.getElementById('video-tree-container');
    const totalBadge = document.getElementById('explorer-total-badge');
    
    if (!folders || folders.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <i class="fa-solid fa-folder-open"></i>
                <p>Không tìm thấy video nào. Hãy kiểm tra đường dẫn thư mục nguồn.</p>
            </div>
        `;
        if (totalBadge) totalBadge.textContent = '0 Video';
        return;
    }

    container.innerHTML = '';
    let totalVideosAcrossFolders = 0;

    folders.forEach(folder => {
        const totalVids = folder.videos.length;
        totalVideosAcrossFolders += totalVids;
        const editedVids = folder.videos.filter(v => v.edited).length;

        const folderEl = document.createElement('div');
        folderEl.className = 'folder-group';
        folderEl.dataset.folderName = folder.name;

        folderEl.innerHTML = `
            <div class="folder-header" title="Bấm để mở/thu gọn thư mục ${escapeHtml(folder.name)}">
                <div class="folder-left">
                    <i class="fa-solid fa-folder-open text-primary folder-icon"></i>
                    <span class="folder-name-text">${escapeHtml(folder.name)}</span>
                </div>
                <div class="folder-right">
                    <span class="badge ${editedVids === totalVids ? 'badge-success' : 'badge-info'}" style="font-size: 10px;">${editedVids}/${totalVids} Đã edit</span>
                    <i class="fa-solid fa-chevron-down folder-chevron"></i>
                </div>
            </div>
            <div class="folder-items-list"></div>
        `;

        const listEl = folderEl.querySelector('.folder-items-list');

        folder.videos.forEach(video => {
            const itemEl = document.createElement('div');
            itemEl.className = `video-tree-item ${video.edited ? 'is-edited' : 'is-unedited'}`;
            itemEl.dataset.videoTitle = video.title.toLowerCase();
            itemEl.dataset.channelName = folder.name.toLowerCase();

            const badgeHtml = video.edited 
                ? '<span class="badge-status edited"><i class="fa-solid fa-check"></i> Đã edit</span>'
                : '<span class="badge-status unedited"><i class="fa-regular fa-circle"></i> Chưa edit</span>';

            itemEl.innerHTML = `
                <div class="video-item-left">
                    <label class="custom-checkbox">
                        <input type="checkbox" class="video-checkbox" data-path="${escapeAttr(video.path)}" data-title="${escapeAttr(video.title)}" data-edited="${video.edited}" data-channel="${escapeAttr(folder.name)}">
                        <span class="checkmark"></span>
                    </label>
                    <span class="video-title-truncate" title="${escapeAttr(video.title)}">${escapeHtml(video.title)}</span>
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
                                    itemEl.querySelector('div:last-child').innerHTML = '<span class="badge-status unedited"><i class="fa-regular fa-circle"></i> Chưa edit</span>';
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

        // Folder accordion collapse toggle
        folderEl.querySelector('.folder-header').addEventListener('click', (e) => {
            if (e.target.tagName === 'INPUT' || e.target.closest('.custom-checkbox')) return;
            folderEl.classList.toggle('is-collapsed');
            const icon = folderEl.querySelector('.folder-icon');
            if (icon) {
                icon.className = folderEl.classList.contains('is-collapsed') 
                    ? 'fa-solid fa-folder text-muted folder-icon' 
                    : 'fa-solid fa-folder-open text-primary folder-icon';
            }
        });

        container.appendChild(folderEl);
    });

    if (totalBadge) totalBadge.textContent = `${totalVideosAcrossFolders} Video`;
    
    // Apply current filter & search
    applyVideoTreeFilters();
    initExplorerControls();
}

function updateExplorerStats(folders) {
    let totalVideos = 0;
    folders.forEach(f => totalVideos += f.videos.length);
    const badge = document.getElementById('explorer-total-badge');
    if (badge) badge.textContent = `${totalVideos} Video`;
    document.getElementById('selected-count-badge').textContent = selectedVideos.size;
}

function filterVideoTree(filter) {
    currentVideoTreeFilter = filter;
    applyVideoTreeFilters();
}

function applyVideoTreeFilters() {
    const filter = currentVideoTreeFilter;
    const search = currentVideoTreeSearch.trim().toLowerCase();
    const folderGroups = document.querySelectorAll('.folder-group');

    folderGroups.forEach(folderEl => {
        const items = folderEl.querySelectorAll('.video-tree-item');
        let visibleCountInFolder = 0;

        items.forEach(item => {
            let matchesStatus = true;
            if (filter === 'unedited') {
                matchesStatus = item.classList.contains('is-unedited');
            } else if (filter === 'edited') {
                matchesStatus = item.classList.contains('is-edited');
            }

            let matchesSearch = true;
            if (search) {
                const title = item.dataset.videoTitle || '';
                const channel = item.dataset.channelName || '';
                matchesSearch = title.includes(search) || channel.includes(search);
            }

            if (matchesStatus && matchesSearch) {
                item.style.display = 'flex';
                visibleCountInFolder++;
            } else {
                item.style.display = 'none';
            }
        });

        // Hide empty folder group if no matching videos inside
        if (visibleCountInFolder > 0) {
            folderEl.style.display = 'block';
        } else {
            folderEl.style.display = 'none';
        }
    });
}

let explorerControlsInitialized = false;
function initExplorerControls() {
    if (explorerControlsInitialized) return;
    explorerControlsInitialized = true;

    // 1. Search Box input & clear
    const searchInput = document.getElementById('input-explorer-search');
    const clearBtn = document.getElementById('btn-clear-explorer-search');

    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            currentVideoTreeSearch = e.target.value;
            if (clearBtn) {
                if (currentVideoTreeSearch) clearBtn.classList.remove('hidden');
                else clearBtn.classList.add('hidden');
            }
            applyVideoTreeFilters();
        });
    }

    if (clearBtn) {
        clearBtn.addEventListener('click', () => {
            if (searchInput) {
                searchInput.value = '';
                currentVideoTreeSearch = '';
                clearBtn.classList.add('hidden');
                applyVideoTreeFilters();
            }
        });
    }

    // 2. Toggle Collapse All Folders
    const btnToggleAll = document.getElementById('btn-toggle-all-folders');
    if (btnToggleAll) {
        let allCollapsed = false;
        btnToggleAll.addEventListener('click', () => {
            allCollapsed = !allCollapsed;
            const folders = document.querySelectorAll('.folder-group');
            folders.forEach(f => {
                const icon = f.querySelector('.folder-icon');
                if (allCollapsed) {
                    f.classList.add('is-collapsed');
                    if (icon) icon.className = 'fa-solid fa-folder text-muted folder-icon';
                } else {
                    f.classList.remove('is-collapsed');
                    if (icon) icon.className = 'fa-solid fa-folder-open text-primary folder-icon';
                }
            });
            btnToggleAll.title = allCollapsed ? 'Mở rộng tất cả thư mục' : 'Thu gọn tất cả thư mục';
        });
    }

    // 3. Collapse/Expand Explorer Panel
    const btnCollapsePanel = document.getElementById('btn-collapse-explorer-panel');
    const explorerPanel = document.getElementById('video-explorer-panel');
    const iconCollapse = document.getElementById('icon-collapse-explorer');

    if (btnCollapsePanel && explorerPanel) {
        btnCollapsePanel.addEventListener('click', () => {
            explorerPanel.classList.toggle('is-collapsed');
            if (iconCollapse) {
                iconCollapse.className = explorerPanel.classList.contains('is-collapsed')
                    ? 'fa-solid fa-chevron-down'
                    : 'fa-solid fa-chevron-up';
            }
        });
    }

    // 4. Resize Handle for Video Tree Container (Thanh kéo chiều cao)
    const resizeHandle = document.getElementById('explorer-resize-handle');
    const treeContainer = document.getElementById('video-tree-container');

    if (resizeHandle && treeContainer) {
        let isDragging = false;
        let startY = 0;
        let startHeight = 0;

        resizeHandle.addEventListener('mousedown', (e) => {
            isDragging = true;
            startY = e.clientY;
            startHeight = treeContainer.offsetHeight;
            resizeHandle.classList.add('is-dragging');
            document.body.style.cursor = 'ns-resize';
            document.body.style.userSelect = 'none';
        });

        document.addEventListener('mousemove', (e) => {
            if (!isDragging) return;
            const deltaY = e.clientY - startY;
            const newHeight = Math.max(220, Math.min(850, startHeight + deltaY));
            treeContainer.style.height = `${newHeight}px`;
            treeContainer.style.maxHeight = `${newHeight}px`;
        });

        document.addEventListener('mouseup', () => {
            if (isDragging) {
                isDragging = false;
                resizeHandle.classList.remove('is-dragging');
                document.body.style.cursor = '';
                document.body.style.userSelect = '';
            }
        });
    }
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
    let target = folderPath;
    if (!target) {
        target = document.getElementById('dest-drive-link')?.value?.trim() || accountsData.dest_path || 'D:/Antigravity/tiktok_running/output_product';
    }
    fetch('/api/open_folder', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: target })
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
        const adspowerId = document.getElementById('input-acc-adspower')?.value.trim() || '';
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
            adspower_id: adspowerId,
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

    // Quick select AdsPower profile
    const selectAdsQuick = document.getElementById('select-acc-adspower-quick');
    if (selectAdsQuick) {
        selectAdsQuick.addEventListener('change', (e) => {
            if (e.target.value) {
                const inputAds = document.getElementById('input-acc-adspower');
                if (inputAds) inputAds.value = e.target.value;
            }
        });
    }

    const btnRefreshAdsProfiles = document.getElementById('btn-refresh-adspower-profiles');
    if (btnRefreshAdsProfiles) {
        btnRefreshAdsProfiles.addEventListener('click', () => {
            if (typeof fetchAdsPowerProfiles === 'function') {
                fetchAdsPowerProfiles(true);
            }
        });
    }
    
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
    if (document.getElementById('input-acc-adspower')) document.getElementById('input-acc-adspower').value = '';
    if (document.getElementById('select-acc-adspower-quick')) document.getElementById('select-acc-adspower-quick').value = '';
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
            
        const adspowerDisplay = (acc.adspower_id || acc.adspower_serial)
            ? `<div style="margin-top:3px;"><span class="badge-adspower" title="AdsPower Profile ID"><i class="fa-solid fa-bolt"></i> ${escapeHtml(acc.adspower_id || acc.adspower_serial)}</span></div>`
            : `<div style="margin-top:3px;"><span style="font-size:10px; opacity:0.6;"><i class="fa-solid fa-bolt"></i> Auto</span></div>`;

        const ipDisplay = `
            <div><span class="badge-ip" title="Original IP"><i class="fa-solid fa-house"></i> ${acc.original_ip || 'No IP'}</span></div>
            <div><span class="badge-ip" title="Nurtured IP"><i class="fa-solid fa-network-wired"></i> ${acc.build_up_ip || 'No IP'}</span></div>
            ${adspowerDisplay}
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
    if (document.getElementById('input-acc-adspower')) {
        document.getElementById('input-acc-adspower').value = acc.adspower_id || acc.adspower_serial || '';
    }
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

    const btnSelectAllPending = document.getElementById('btn-pub-select-all-pending');
    if (btnSelectAllPending) {
        btnSelectAllPending.addEventListener('click', () => {
            const allChks = document.querySelectorAll('.part-pill-chk');
            let hasAny = false;
            allChks.forEach(chk => {
                const pill = chk.closest('.part-pill');
                const isPosted = pill && pill.classList.contains('part-chip-posted');
                if (!isPosted) {
                    chk.checked = true;
                    if (pill) pill.classList.add('is-selected');
                    hasAny = true;
                }
            });
            updateGlobalSelectedPartsCount();
            if (!hasAny) {
                alert('Tất cả các part đã được đăng!');
            }
        });
    }

    const btnBatchPostSelected = document.getElementById('btn-pub-batch-post-selected');
    if (btnBatchPostSelected) {
        btnBatchPostSelected.addEventListener('click', () => {
            const checkedChks = Array.from(document.querySelectorAll('.part-pill-chk:checked'));
            if (checkedChks.length === 0) {
                alert('Vui lòng tích chọn ít nhất 1 Part trên danh sách để đăng!');
                return;
            }
            const partsList = checkedChks.map(chk => ({
                clip_key: chk.dataset.clipKey,
                channel: chk.dataset.channel,
                title: chk.dataset.title,
                file_path: chk.dataset.filePath,
                label: chk.dataset.partLabel
            }));
            handleBatchPostGlobalParts(partsList);
        });
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

        // Parts buttons: Tinh gọn UX/UI (Checkbox phía trước + Tên Part + Icon trạng thái phía sau)
        let partsHtml = '';
        if (clip.parts && clip.parts.length > 0) {
            partsHtml = `
                <div class="finished-parts-chips" style="margin-top: 6px;">
                    ${clip.parts.map((p, idx) => {
                        const partLabel = p.label || `Part ${idx + 1}`;
                        const isPartPosted = p.posted;
                        const partBadgeClass = isPartPosted ? 'part-chip-posted' : '';
                        const partFilePath = p.file_path || '';
                        return `
                            <div class="part-pill ${partBadgeClass}" data-part="${partLabel}">
                                <label class="part-pill-chk-label" title="Tích chọn để đăng ${partLabel}">
                                    <input type="checkbox" class="part-pill-chk" data-clip-key="${escapeAttr(clip.key)}" data-part-label="${partLabel}" data-file-path="${escapeAttr(partFilePath)}" data-channel="${escapeAttr(clip.channel)}" data-title="${escapeAttr(clip.title)}">
                                </label>
                                <button type="button" class="part-pill-preview" onclick="playFinishedVideo('${encodeURIComponent(p.url)}', '${escapeAttr(clip.title)} - ${partLabel}')" title="Xem trước ${escapeAttr(p.name || partLabel)}">
                                    <i class="fa-solid fa-play" style="font-size: 9px;"></i> ${escapeHtml(partLabel)}
                                </button>
                                <button type="button" class="part-pill-toggle" onclick="handleTogglePartPost('${escapeAttr(clip.key)}', '${escapeAttr(clip.channel)}', '${escapeAttr(clip.title)}', '${partLabel}', ${!isPartPosted})" title="${isPartPosted ? 'Đã đăng ' + (p.posted_at || '') + ' (Bấm để hủy)' : 'Chưa đăng (Bấm để đánh dấu Đã Đăng)'}">
                                    <i class="fa-solid ${isPartPosted ? 'fa-circle-check text-success' : 'fa-circle-dot text-muted'}"></i>
                                </button>
                            </div>
                        `;
                    }).join('')}
                </div>
            `;
        }

        const postedTagHtml = clip.posted 
            ? `<span class="pub-posted-tag"><i class="fa-solid fa-circle-check"></i> Đã đăng đủ part ${clip.posted_at ? `(${clip.posted_at})` : ''}</span>`
            : '';

        row.innerHTML = `
            <div class="pub-clip-left">
                <button type="button" class="pub-clip-checkbox-btn" title="${clip.posted ? 'Bấm để đánh dấu Chưa Đăng tất cả part' : 'Bấm để đánh dấu ĐÃ ĐĂNG tất cả part'}" onclick="handleToggleClipPost('${escapeAttr(clip.key)}', '${escapeAttr(clip.channel)}', '${escapeAttr(clip.title)}', ${!clip.posted})">
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
                <button class="btn btn-sm btn-post-auto" onclick="handleSelectPartToPost('${escapeAttr(clip.key)}', '${escapeAttr(clip.channel)}', '${escapeAttr(clip.title)}', '${escapeAttr(clip.path || '')}')" title="Đăng các Part đã chọn hoặc chọn Part">
                    <i class="fa-brands fa-tiktok"></i> Đăng TikTok
                </button>
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

    // Lắng nghe sự kiện click checkbox trên từng Part Pill
    container.querySelectorAll('.part-pill-chk').forEach(chk => {
        chk.addEventListener('change', () => {
            const pill = chk.closest('.part-pill');
            if (chk.checked) {
                pill.classList.add('is-selected');
            } else {
                pill.classList.remove('is-selected');
            }
            updateGlobalSelectedPartsCount();
        });
    });

    updateGlobalSelectedPartsCount();
}

function updateGlobalSelectedPartsCount() {
    const totalSelected = document.querySelectorAll('.part-pill-chk:checked').length;
    const badgeEl = document.getElementById('pub-selected-parts-total');
    if (badgeEl) badgeEl.textContent = totalSelected;
}

// Xử lý khi bấm nút Đăng TikTok tổng: Mở Part Selection Modal hỗ trợ Đăng Tất Cả & Multi-select Part
function handleSelectPartToPost(clipKey, channel, title, videoPath) {
    if (!activePublishingAccountName) {
        alert('Vui lòng chọn tài khoản TikTok cần đăng!');
        return;
    }
    const accounts = publishingMatrixData.accounts || [];
    const acc = accounts.find(a => a.account_name === activePublishingAccountName);
    if (!acc) return;
    const clip = acc.clips?.find(c => c.key === clipKey);
    if (!clip) return;

    if (!clip.parts || clip.parts.length <= 1) {
        // Chỉ có 1 part hoặc không phân part -> đăng trực tiếp
        const singlePart = clip.parts && clip.parts.length === 1 ? clip.parts[0] : null;
        handleAutoPostToTikTok(clipKey, channel, title, videoPath, singlePart?.file_path || '', singlePart?.label || '');
        return;
    }

    // Mở Part Selection Modal
    const modal = document.getElementById('part-selection-modal');
    const titleEl = document.getElementById('part-select-clip-title');
    const accEl = document.getElementById('part-select-target-account');
    const countEl = document.getElementById('part-select-count');
    const listEl = document.getElementById('part-selection-list');
    const selectedCountEl = document.getElementById('selected-parts-count');
    const btnSelectAll = document.getElementById('btn-select-all-parts');
    const btnSelectPending = document.getElementById('btn-select-pending-parts');
    const btnDeselectAll = document.getElementById('btn-deselect-all-parts');
    const btnPostAll = document.getElementById('btn-post-all-parts-direct');
    const btnPostSelected = document.getElementById('btn-post-selected-parts');
    const btnCancel = document.getElementById('btn-cancel-part-select');
    const btnClose = document.getElementById('btn-close-part-select-modal');

    titleEl.textContent = title;
    accEl.textContent = `Đăng lên: @${acc.account_name} (AdsPower: ${acc.adspower_id || acc.adspower_serial || 'Default'} | IP: ${acc.build_up_ip || acc.original_ip || 'US'})`;
    countEl.textContent = clip.parts.length;

    const updateSelectedCount = () => {
        const checkedBoxes = listEl.querySelectorAll('.part-select-checkbox:checked');
        selectedCountEl.textContent = checkedBoxes.length;
        btnPostSelected.disabled = checkedBoxes.length === 0;
        if (checkedBoxes.length === 0) {
            btnPostSelected.style.opacity = '0.5';
        } else {
            btnPostSelected.style.opacity = '1';
        }
    };

    // Render danh sách part (Mặc định không tích chọn part nào)
    listEl.innerHTML = clip.parts.map((p, idx) => {
        const isPosted = !!p.posted;
        const pLabel = p.label || `Part ${idx + 1}`;
        return `
            <div class="part-select-item ${isPosted ? 'is-posted' : ''}" data-idx="${idx}">
                <label class="part-select-label" for="part-chk-${idx}">
                    <input type="checkbox" id="part-chk-${idx}" class="part-select-checkbox" data-idx="${idx}">
                    <span class="part-select-num-badge">${escapeHtml(pLabel)}</span>
                    <span class="part-select-filename" title="${escapeAttr(p.name || '')}">${escapeHtml(p.name || 'part_' + (idx + 1) + '.mp4')}</span>
                </label>
                <span class="part-select-status-badge ${isPosted ? 'posted' : 'pending'}">
                    ${isPosted ? '<i class="fa-solid fa-check"></i> Đã đăng' : '<i class="fa-regular fa-clock"></i> Chưa đăng'}
                </span>
            </div>
        `;
    }).join('');

    updateSelectedCount();

    // Lắng nghe thay đổi checkbox
    listEl.querySelectorAll('.part-select-checkbox').forEach(chk => {
        chk.addEventListener('change', () => {
            const item = chk.closest('.part-select-item');
            if (chk.checked) {
                item.classList.add('selected');
            } else {
                item.classList.remove('selected');
            }
            updateSelectedCount();
        });
    });

    btnSelectAll.onclick = () => {
        listEl.querySelectorAll('.part-select-checkbox').forEach(chk => {
            chk.checked = true;
            chk.closest('.part-select-item').classList.add('selected');
        });
        updateSelectedCount();
    };

    btnSelectPending.onclick = () => {
        listEl.querySelectorAll('.part-select-item').forEach(item => {
            const chk = item.querySelector('.part-select-checkbox');
            const isPosted = item.classList.contains('is-posted');
            chk.checked = !isPosted;
            if (chk.checked) item.classList.add('selected');
            else item.classList.remove('selected');
        });
        updateSelectedCount();
    };

    btnDeselectAll.onclick = () => {
        listEl.querySelectorAll('.part-select-checkbox').forEach(chk => {
            chk.checked = false;
            chk.closest('.part-select-item').classList.remove('selected');
        });
        updateSelectedCount();
    };

    const closePartModal = () => {
        modal.classList.add('hidden');
    };

    btnCancel.onclick = closePartModal;
    btnClose.onclick = closePartModal;

    // Option 1: Đăng TẤT CẢ Part theo thứ tự
    btnPostAll.onclick = () => {
        closePartModal();
        handleBatchPostParts(clipKey, channel, title, videoPath, clip.parts);
    };

    // Option 2: Đăng các Part ĐÃ CHỌN theo thứ tự
    btnPostSelected.onclick = () => {
        const checkedIndices = Array.from(listEl.querySelectorAll('.part-select-checkbox:checked')).map(chk => parseInt(chk.dataset.idx));
        if (checkedIndices.length === 0) {
            alert('Vui lòng chọn ít nhất 1 Part để đăng!');
            return;
        }
        const selectedParts = checkedIndices.map(i => clip.parts[i]).filter(Boolean);
        closePartModal();
        handleBatchPostParts(clipKey, channel, title, videoPath, selectedParts);
    };

    modal.classList.remove('hidden');
}

// Hàm thực thi đăng hàng loạt (Batch sequential post) nhiều Part
async function handleBatchPostParts(clipKey, channel, title, videoPath, partsToPost) {
    if (!partsToPost || partsToPost.length === 0) return;

    if (partsToPost.length === 1) {
        const p = partsToPost[0];
        handleAutoPostToTikTok(clipKey, channel, title, videoPath, p.file_path || '', p.label || 'Part 1');
        return;
    }

    if (!activePublishingAccountName) {
        alert('Vui lòng chọn tài khoản TikTok cần đăng!');
        return;
    }

    const accounts = publishingMatrixData.accounts || [];
    const acc = accounts.find(a => a.account_name === activePublishingAccountName);
    if (!acc) return;

    const modal = document.getElementById('posting-progress-modal');
    const modalTitle = document.getElementById('posting-modal-title');
    const metaAcc = document.getElementById('posting-meta-acc');
    const metaIp = document.getElementById('posting-meta-ip');
    const metaProfile = document.getElementById('posting-meta-profile');
    const metaClipTitle = document.getElementById('posting-meta-clip-title');
    const logsWindow = document.getElementById('posting-terminal-logs');
    const btnFinish = document.getElementById('btn-finish-posting-modal');
    const btnClose = document.getElementById('btn-close-posting-modal');

    const stepHma = document.getElementById('step-hma');
    const stepAds = document.getElementById('step-ads');
    const stepUpload = document.getElementById('step-upload');
    const stepDone = document.getElementById('step-done');

    const setStepState = (el, statusText, state = 'active') => {
        el.className = `posting-step ${state}`;
        const statusSpan = el.querySelector('.step-status');
        if (statusSpan) statusSpan.textContent = statusText;
    };

    logsWindow.innerHTML = '';
    const appendLog = (msg, isError = false) => {
        const line = document.createElement('div');
        line.className = `log-line ${isError ? 'text-danger' : ''}`;
        line.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
        logsWindow.appendChild(line);
        logsWindow.scrollTop = logsWindow.scrollHeight;
    };

    metaAcc.textContent = `@${acc.account_name}`;
    metaIp.textContent = acc.build_up_ip || acc.original_ip || 'Mặc định';
    metaProfile.textContent = acc.adspower_id || acc.adspower_serial || 'Tự động';

    modal.classList.remove('hidden');
    btnFinish.disabled = true;
    btnClose.onclick = () => modal.classList.add('hidden');
    btnFinish.onclick = () => modal.classList.add('hidden');

    appendLog(`🚀 BẮT ĐẦU ĐĂNG TUẦN TỰ ${partsToPost.length} PART CHO CLIP: "${title}"`);
    appendLog(`📋 Danh sách part: ${partsToPost.map(p => p.label || p.name).join(', ')}`);

    let successCount = 0;

    for (let i = 0; i < partsToPost.length; i++) {
        const currentPart = partsToPost[i];
        const partLabel = currentPart.label || `Part ${i + 1}`;
        const displayUploadTitle = `${title} (${partLabel})`;

        modalTitle.textContent = `[${i + 1}/${partsToPost.length}] Đang Đăng: "${displayUploadTitle}"`;
        metaClipTitle.textContent = displayUploadTitle;

        setStepState(stepHma, 'Đang chuẩn bị...', 'active');
        setStepState(stepAds, 'Chờ...', '');
        setStepState(stepUpload, 'Chờ...', '');
        setStepState(stepDone, 'Chờ...', '');

        appendLog(`\n--------------------------------------------------`);
        appendLog(`▶️ [TIẾN TRÌNH ${i + 1}/${partsToPost.length}] Bắt đầu tải lên ${partLabel}...`);

        try {
            setTimeout(() => {
                if (stepHma.classList.contains('active')) {
                    setStepState(stepHma, 'Đã chuyển IP', 'done');
                    setStepState(stepAds, 'Đang mở profile...', 'active');
                }
            }, 1500);

            setTimeout(() => {
                if (stepAds.classList.contains('active')) {
                    setStepState(stepAds, 'Đã mở Chrome', 'done');
                    setStepState(stepUpload, 'Đang tải lên...', 'active');
                }
            }, 3500);

            const res = await fetch('/api/publishing/post_to_tiktok', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    account_name: activePublishingAccountName,
                    clip_key: clipKey,
                    channel: channel,
                    title: title,
                    video_file: currentPart.file_path || '',
                    part_label: partLabel
                })
            });

            const data = await res.json();

            if (data.step_logs && Array.isArray(data.step_logs)) {
                data.step_logs.forEach(logText => appendLog(logText));
            }

            if (data.success) {
                successCount++;
                setStepState(stepHma, 'Hoàn thành', 'done');
                setStepState(stepAds, 'Hoàn thành', 'done');
                setStepState(stepUpload, 'Đã tải lên', 'done');
                setStepState(stepDone, 'Thành công', 'done');
                appendLog(`✅ [${i + 1}/${partsToPost.length}] ${partLabel} ĐÃ ĐĂNG THÀNH CÔNG!`);

                // Cập nhật trạng thái hiển thị
                fetchPublishingMatrix();

                // Nếu còn part tiếp theo -> Chờ 5 giây trước khi tiếp tục
                if (i < partsToPost.length - 1) {
                    appendLog(`⏳ Đang nghỉ 5 giây trước khi đăng Part tiếp theo...`);
                    await new Promise(resolve => setTimeout(resolve, 5000));
                }
            } else {
                setStepState(stepDone, 'Lỗi', 'error');
                appendLog(`❌ [${i + 1}/${partsToPost.length}] Lỗi khi đăng ${partLabel}: ${data.error || 'Thất bại'}`, true);
            }
        } catch (err) {
            setStepState(stepDone, 'Lỗi mạng', 'error');
            appendLog(`❌ [${i + 1}/${partsToPost.length}] Ngoại lệ: ${err.message}`, true);
        }
    }

    // Kết thúc toàn bộ tiến trình
    appendLog(`\n==================================================`);
    appendLog(`🎉 KẾT THÚC TIẾN TRÌNH: Đã đăng thành công ${successCount}/${partsToPost.length} Part!`);
    modalTitle.textContent = `Hoàn tất đăng ${successCount}/${partsToPost.length} Part`;
    btnFinish.disabled = false;
    btnFinish.innerHTML = '<i class="fa-solid fa-check"></i> Đã hoàn tất - Đóng';
    fetchPublishingMatrix();
}

// Đăng hàng loạt danh sách các Part được tích chọn trên nhiều clip
async function handleBatchPostGlobalParts(partsList) {
    if (!partsList || partsList.length === 0) return;

    if (!activePublishingAccountName) {
        alert('Vui lòng chọn tài khoản TikTok cần đăng!');
        return;
    }

    const accounts = publishingMatrixData.accounts || [];
    const acc = accounts.find(a => a.account_name === activePublishingAccountName);
    if (!acc) return;

    const modal = document.getElementById('posting-progress-modal');
    const modalTitle = document.getElementById('posting-modal-title');
    const metaAcc = document.getElementById('posting-meta-acc');
    const metaIp = document.getElementById('posting-meta-ip');
    const metaProfile = document.getElementById('posting-meta-profile');
    const metaClipTitle = document.getElementById('posting-meta-clip-title');
    const logsWindow = document.getElementById('posting-terminal-logs');
    const btnFinish = document.getElementById('btn-finish-posting-modal');
    const btnClose = document.getElementById('btn-close-posting-modal');

    const stepHma = document.getElementById('step-hma');
    const stepAds = document.getElementById('step-ads');
    const stepUpload = document.getElementById('step-upload');
    const stepDone = document.getElementById('step-done');

    const setStepState = (el, statusText, state = 'active') => {
        el.className = `posting-step ${state}`;
        const statusSpan = el.querySelector('.step-status');
        if (statusSpan) statusSpan.textContent = statusText;
    };

    logsWindow.innerHTML = '';
    const appendLog = (msg, isError = false) => {
        const line = document.createElement('div');
        line.className = `log-line ${isError ? 'text-danger' : ''}`;
        line.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
        logsWindow.appendChild(line);
        logsWindow.scrollTop = logsWindow.scrollHeight;
    };

    metaAcc.textContent = `@${acc.account_name}`;
    metaIp.textContent = acc.build_up_ip || acc.original_ip || 'Mặc định';
    metaProfile.textContent = acc.adspower_id || acc.adspower_serial || 'Tự động';

    modal.classList.remove('hidden');
    btnFinish.disabled = true;
    btnClose.onclick = () => modal.classList.add('hidden');
    btnFinish.onclick = () => modal.classList.add('hidden');

    appendLog(`🚀 BẮT ĐẦU ĐĂNG TUẦN TỰ ${partsList.length} PART ĐÃ CHỌN LÊN @${acc.account_name}...`);

    let successCount = 0;

    for (let i = 0; i < partsList.length; i++) {
        const item = partsList[i];
        const displayUploadTitle = `${item.title} (${item.label})`;

        modalTitle.textContent = `[${i + 1}/${partsList.length}] Đang Đăng: "${displayUploadTitle}"`;
        metaClipTitle.textContent = displayUploadTitle;

        setStepState(stepHma, 'Đang chuẩn bị...', 'active');
        setStepState(stepAds, 'Chờ...', '');
        setStepState(stepUpload, 'Chờ...', '');
        setStepState(stepDone, 'Chờ...', '');

        appendLog(`\n--------------------------------------------------`);
        appendLog(`▶️ [TIẾN TRÌNH ${i + 1}/${partsList.length}] Bắt đầu đăng: "${displayUploadTitle}"`);

        try {
            setTimeout(() => {
                if (stepHma.classList.contains('active')) {
                    setStepState(stepHma, 'Đã chuyển IP', 'done');
                    setStepState(stepAds, 'Đang mở profile...', 'active');
                }
            }, 1500);

            setTimeout(() => {
                if (stepAds.classList.contains('active')) {
                    setStepState(stepAds, 'Đã mở Chrome', 'done');
                    setStepState(stepUpload, 'Đang tải lên...', 'active');
                }
            }, 3500);

            const res = await fetch('/api/publishing/post_to_tiktok', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    account_name: activePublishingAccountName,
                    clip_key: item.clip_key,
                    channel: item.channel,
                    title: item.title,
                    video_file: item.file_path || '',
                    part_label: item.label
                })
            });

            const data = await res.json();

            if (data.step_logs && Array.isArray(data.step_logs)) {
                data.step_logs.forEach(logText => appendLog(logText));
            }

            if (data.success) {
                successCount++;
                setStepState(stepHma, 'Hoàn thành', 'done');
                setStepState(stepAds, 'Hoàn thành', 'done');
                setStepState(stepUpload, 'Đã tải lên', 'done');
                setStepState(stepDone, 'Thành công', 'done');
                appendLog(`✅ [${i + 1}/${partsList.length}] ${displayUploadTitle} ĐÃ ĐĂNG THÀNH CÔNG!`);

                fetchPublishingMatrix();

                if (i < partsList.length - 1) {
                    appendLog(`⏳ Nghỉ 5 giây trước khi đăng Part tiếp theo...`);
                    await new Promise(resolve => setTimeout(resolve, 5000));
                }
            } else {
                setStepState(stepDone, 'Lỗi', 'error');
                appendLog(`❌ [${i + 1}/${partsList.length}] Lỗi: ${data.error || 'Thất bại'}`, true);
            }
        } catch (err) {
            setStepState(stepDone, 'Lỗi kết nối', 'error');
            appendLog(`❌ [${i + 1}/${partsList.length}] Ngoại lệ: ${err.message}`, true);
        }
    }

    appendLog(`\n==================================================`);
    appendLog(`🎉 KẾT THÚC: Đã hoàn tất đăng ${successCount}/${partsList.length} Part đã chọn!`);
    modalTitle.textContent = `Hoàn tất đăng ${successCount}/${partsList.length} Part`;
    btnFinish.disabled = false;
    btnFinish.innerHTML = '<i class="fa-solid fa-check"></i> Đã hoàn tất - Đóng';
    fetchPublishingMatrix();
}

async function handleTogglePartPost(clipKey, channel, title, partLabel, posted) {
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
                part_label: partLabel,
                posted: posted
            })
        });
        const data = await res.json();
        if (data.success) {
            fetchPublishingMatrix();
        }
    } catch (err) {
        console.error('Error toggling part status:', err);
    }
}

/* ==========================================================================
   11. TikTok Auto-Posting Interactive Stepper Pipeline
   ========================================================================== */
async function handleAutoPostToTikTok(clipKey, channel, title, videoPath, specificFile = null, partLabel = null) {
    if (!activePublishingAccountName) {
        alert('Vui lòng chọn tài khoản TikTok cần đăng!');
        return;
    }

    const accounts = publishingMatrixData.accounts || [];
    const acc = accounts.find(a => a.account_name === activePublishingAccountName);
    if (!acc) return;

    const displayUploadTitle = (partLabel && !title.includes(partLabel)) ? `${title} (${partLabel})` : title;

    const modal = document.getElementById('posting-progress-modal');
    const modalTitle = document.getElementById('posting-modal-title');
    const metaAcc = document.getElementById('posting-meta-acc');
    const metaIp = document.getElementById('posting-meta-ip');
    const metaProfile = document.getElementById('posting-meta-profile');
    const metaClipTitle = document.getElementById('posting-meta-clip-title');
    const logsWindow = document.getElementById('posting-terminal-logs');
    const btnFinish = document.getElementById('btn-finish-posting-modal');
    const btnClose = document.getElementById('btn-close-posting-modal');

    // Cập nhật thông tin trên Modal
    modalTitle.textContent = `Đang Đăng: "${displayUploadTitle}"`;
    metaAcc.textContent = `@${acc.account_name}`;
    metaIp.textContent = acc.build_up_ip || acc.original_ip || 'Mặc định';
    metaProfile.textContent = acc.adspower_id || acc.adspower_serial || 'Tự động';
    metaClipTitle.textContent = displayUploadTitle;

    // Reset Stepper
    const stepHma = document.getElementById('step-hma');
    const stepAds = document.getElementById('step-ads');
    const stepUpload = document.getElementById('step-upload');
    const stepDone = document.getElementById('step-done');

    const setStepState = (el, statusText, state = 'active') => {
        el.className = `posting-step ${state}`;
        const statusSpan = el.querySelector('.step-status');
        if (statusSpan) statusSpan.textContent = statusText;
    };

    setStepState(stepHma, 'Đang đổi IP...', 'active');
    setStepState(stepAds, 'Chờ...', '');
    setStepState(stepUpload, 'Chờ...', '');
    setStepState(stepDone, 'Chờ...', '');

    logsWindow.innerHTML = '';
    const appendLog = (msg, isError = false) => {
        const line = document.createElement('div');
        line.className = `log-line ${isError ? 'text-danger' : ''}`;
        line.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
        logsWindow.appendChild(line);
        logsWindow.scrollTop = logsWindow.scrollHeight;
    };

    appendLog(`🚀 Bắt đầu quy trình đăng "${displayUploadTitle}" cho tài khoản @${acc.account_name}`);
    if (acc.build_up_ip || acc.original_ip) {
        appendLog(`🛡️ Đang kích hoạt HMA chuyển IP sang: ${acc.build_up_ip || acc.original_ip}...`);
    }

    modal.classList.remove('hidden');
    btnFinish.disabled = true;

    btnClose.onclick = () => {
        modal.classList.add('hidden');
    };
    btnFinish.onclick = () => {
        modal.classList.add('hidden');
    };

    try {
        // Step 1 -> 2 animation cue
        setTimeout(() => {
            if (stepHma.classList.contains('active')) {
                setStepState(stepHma, 'Đã chuyển IP', 'done');
                setStepState(stepAds, 'Đang mở profile...', 'active');
                appendLog(`⚡ Đang kết nối AdsPower Profile: ${acc.adspower_id || acc.adspower_serial || 'Default'}...`);
            }
        }, 1500);

        setTimeout(() => {
            if (stepAds.classList.contains('active')) {
                setStepState(stepAds, 'Đã mở Chrome', 'done');
                setStepState(stepUpload, 'Đang tải lên...', 'active');
                appendLog('🌐 Đang tải lên video thành phẩm và điền tiêu đề + hashtags...');
            }
        }, 3500);

        const res = await fetch('/api/publishing/post_to_tiktok', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                account_name: activePublishingAccountName,
                clip_key: clipKey,
                channel: channel,
                title: title,
                video_file: specificFile || '',
                part_label: partLabel || ''
            })
        });

        const data = await res.json();

        if (data.step_logs && Array.isArray(data.step_logs)) {
            data.step_logs.forEach(logText => appendLog(logText));
        }

        if (data.success) {
            setStepState(stepHma, 'Hoàn thành', 'done');
            setStepState(stepAds, 'Hoàn thành', 'done');
            setStepState(stepUpload, 'Đã tải lên', 'done');
            setStepState(stepDone, 'Thành công!', 'done');
            appendLog(`🎉 HOÀN TẤT ĐĂNG "${displayUploadTitle}" LÊN TIKTOK THÀNH CÔNG!`);

            btnFinish.disabled = false;
            btnFinish.innerHTML = '<i class="fa-solid fa-check"></i> Đăng thành công - Đóng';

            // Cập nhật lại Publishing Matrix để hiển thị trạng thái mới nhất
            fetchPublishingMatrix();
        } else {
            setStepState(stepDone, 'Thất bại', 'error');
            appendLog(`❌ Lỗi: ${data.error || 'Quá trình đăng video thất bại'}`, true);
            btnFinish.disabled = false;
            btnFinish.innerHTML = '<i class="fa-solid fa-xmark"></i> Đóng';
        }
    } catch (err) {
        setStepState(stepDone, 'Lỗi kết nối', 'error');
        appendLog(`❌ Lỗi kết nối máy chủ: ${err.message}`, true);
        btnFinish.disabled = false;
        btnFinish.innerHTML = '<i class="fa-solid fa-xmark"></i> Đóng';
    }
}


/* ==========================================================================
   12. Section: Settings Manager (AdsPower, HMA VPN & Workspace Paths)
   ========================================================================== */
let systemSettings = {
    adspower: { api_url: "http://local.adspower.net:50325", api_key: "" },
    hma: { cli_path: "", enabled: true, switch_mode: "country", wait_seconds_after_switch: 5 },
    tiktok_upload: { auto_submit: true, close_browser_after_finish: false, wait_timeout: 60 }
};
let availableAdsPowerProfiles = [];

function initSettingsManager() {
    const btnSaveAll = document.getElementById('btn-save-all-settings');
    const btnSavePaths = document.getElementById('btn-save-paths');
    const btnTestAdsPower = document.getElementById('btn-test-adspower');
    const btnTestHmaIp = document.getElementById('btn-test-hma-ip');
    const btnTestHmaChange = document.getElementById('btn-test-hma-change');
    const btnHmaDisconnect = document.getElementById('btn-hma-disconnect');
    const btnAutoDetectHma = document.getElementById('btn-auto-detect-hma');
    const btnPickSource = document.getElementById('btn-pick-source');
    const btnPickDest = document.getElementById('btn-pick-dest');
    const btnPickHma = document.getElementById('btn-pick-hma');

    if (btnSaveAll) btnSaveAll.addEventListener('click', saveAllSettings);
    if (btnSavePaths) btnSavePaths.addEventListener('click', saveAllSettings);
    if (btnTestAdsPower) btnTestAdsPower.addEventListener('click', () => testAdsPowerConnection(false));
    if (btnTestHmaIp) btnTestHmaIp.addEventListener('click', () => checkHmaIp(false));
    if (btnTestHmaChange) btnTestHmaChange.addEventListener('click', testHmaChangeIp);
    if (btnHmaDisconnect) btnHmaDisconnect.addEventListener('click', disconnectHma);
    if (btnAutoDetectHma) btnAutoDetectHma.addEventListener('click', autoDetectHma);

    if (btnPickSource) {
        btnPickSource.addEventListener('click', async () => {
            const folder = await pickLocalFolder();
            if (folder) document.getElementById('source-drive-link').value = folder;
        });
    }

    if (btnPickDest) {
        btnPickDest.addEventListener('click', async () => {
            const folder = await pickLocalFolder();
            if (folder) document.getElementById('dest-drive-link').value = folder;
        });
    }

    if (btnPickHma) {
        btnPickHma.addEventListener('click', async () => {
            const folder = await pickLocalFolder();
            if (folder) document.getElementById('input-hma-path').value = folder;
        });
    }

    fetchSettings();
}

async function fetchSettings() {
    try {
        const res = await fetch('/api/settings');
        const data = await res.json();
        systemSettings = data;

        // AdsPower fields
        const adspowerUrl = document.getElementById('input-adspower-url');
        const adspowerKey = document.getElementById('input-adspower-key');
        if (adspowerUrl) adspowerUrl.value = data.adspower?.api_url || 'http://local.adspower.net:50325';
        if (adspowerKey) adspowerKey.value = data.adspower?.api_key || '';

        // HMA fields
        const hmaPath = document.getElementById('input-hma-path');
        const hmaMode = document.getElementById('select-hma-mode');
        const hmaWait = document.getElementById('input-hma-wait');
        if (hmaPath) {
            hmaPath.value = data.hma?.cli_path || data.hma_detected_path || '';
        }
        if (hmaMode) hmaMode.value = data.hma?.switch_mode || 'country';
        if (hmaWait) hmaWait.value = data.hma?.wait_seconds_after_switch || 5;

        // TikTok preferences
        const postMode = document.getElementById('select-tiktok-post-mode');
        const closeBrowser = document.getElementById('select-tiktok-close-browser');
        const timeout = document.getElementById('input-tiktok-timeout');
        if (postMode) postMode.value = data.tiktok_upload?.auto_submit ? 'auto_post' : 'draft';
        if (closeBrowser) closeBrowser.value = data.tiktok_upload?.close_browser_after_finish ? 'yes' : 'no';
        if (timeout) timeout.value = data.tiktok_upload?.wait_timeout || 60;

        // Tự động kiểm tra AdsPower và IP ngầm
        testAdsPowerConnection(true);
        checkHmaIp(true);
    } catch (err) {
        console.error('Error fetching settings:', err);
    }
}

async function saveAllSettings() {
    const sourcePath = document.getElementById('source-drive-link')?.value.trim() || '';
    const destPath = document.getElementById('dest-drive-link')?.value.trim() || '';
    const adspowerUrl = document.getElementById('input-adspower-url')?.value.trim() || 'http://local.adspower.net:50325';
    const adspowerKey = document.getElementById('input-adspower-key')?.value.trim() || '';
    const hmaPath = document.getElementById('input-hma-path')?.value.trim() || '';
    const hmaMode = document.getElementById('select-hma-mode')?.value || 'country';
    const hmaWait = parseInt(document.getElementById('input-hma-wait')?.value || 5);
    const postMode = document.getElementById('select-tiktok-post-mode')?.value || 'auto_post';
    const closeBrowser = document.getElementById('select-tiktok-close-browser')?.value === 'yes';
    const timeout = parseInt(document.getElementById('input-tiktok-timeout')?.value || 60);

    const payload = {
        adspower: {
            api_url: adspowerUrl,
            api_key: adspowerKey
        },
        hma: {
            cli_path: hmaPath,
            enabled: true,
            switch_mode: hmaMode,
            wait_seconds_after_switch: hmaWait
        },
        tiktok_upload: {
            auto_submit: (postMode === 'auto_post'),
            close_browser_after_finish: closeBrowser,
            wait_timeout: timeout
        }
    };

    try {
        // 1. Lưu cài đặt hệ thống
        const res = await fetch('/api/settings/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        // 2. Lưu Workspace paths vào accounts.json
        if (typeof accountsData !== 'undefined') {
            accountsData.source_path = sourcePath;
            accountsData.dest_path = destPath;
            await saveAccountsToBackend();
        }

        const data = await res.json();
        if (data.success) {
            alert('🎉 Đã lưu toàn bộ cấu hình Settings & Workspaces thành công!');
        } else {
            alert('Lỗi khi lưu cài đặt!');
        }
    } catch (err) {
        alert('Lỗi kết nối khi lưu cài đặt: ' + err.message);
    }
}

async function testAdsPowerConnection(silent = false) {
    const url = document.getElementById('input-adspower-url')?.value.trim() || 'http://local.adspower.net:50325';
    const key = document.getElementById('input-adspower-key')?.value.trim() || '';
    const badge = document.getElementById('adspower-status-badge');
    const countSpan = document.getElementById('adspower-profiles-count');
    const previewDiv = document.getElementById('adspower-profiles-preview');

    if (badge) {
        badge.innerHTML = '<span class="status-dot warning" style="width: 6px; height: 6px;"></span> Đang kiểm tra...';
    }

    try {
        const res = await fetch('/api/adspower/test', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ api_url: url, api_key: key })
        });
        const data = await res.json();

        if (data.connected) {
            if (badge) {
                badge.className = 'badge badge-success';
                badge.innerHTML = '<span class="status-dot online" style="width: 6px; height: 6px;"></span> AdsPower Online';
            }

            availableAdsPowerProfiles = data.profiles || [];
            if (countSpan) countSpan.textContent = `${availableAdsPowerProfiles.length} Profiles`;

            // Populate preview
            if (previewDiv && availableAdsPowerProfiles.length > 0) {
                previewDiv.style.display = 'block';
                previewDiv.innerHTML = availableAdsPowerProfiles.slice(0, 8).map(p => `
                    <div style="padding: 2px 0; border-bottom: 1px dashed rgba(255,255,255,0.05); display: flex; justify-content: space-between;">
                        <span><strong>#${escapeHtml(p.serial_number)}</strong> ${escapeHtml(p.name)} (${escapeHtml(p.user_id)})</span>
                        <span style="opacity: 0.6;">${escapeHtml(p.country || p.ip || 'No IP')}</span>
                    </div>
                `).join('');
            }

            // Populate account dropdown
            populateAdsPowerSelectDropdown(availableAdsPowerProfiles);

            if (!silent) {
                alert(`✅ Kết nối AdsPower thành công!\nTìm thấy ${availableAdsPowerProfiles.length} profiles.`);
            }
        } else {
            if (badge) {
                badge.className = 'badge badge-danger';
                badge.innerHTML = '<span class="status-dot offline" style="width: 6px; height: 6px;"></span> AdsPower Offline';
            }
            if (!silent) {
                alert(`❌ ${data.message || 'Không thể kết nối đến AdsPower. Hãy mở ứng dụng AdsPower và bật Local API.'}`);
            }
        }
    } catch (err) {
        if (badge) {
            badge.className = 'badge badge-danger';
            badge.innerHTML = '<span class="status-dot offline" style="width: 6px; height: 6px;"></span> Lỗi kết nối';
        }
        if (!silent) alert('Lỗi kết nối: ' + err.message);
    }
}

async function fetchAdsPowerProfiles(populateSelect = true) {
    try {
        const url = document.getElementById('input-adspower-url')?.value.trim() || '';
        const key = document.getElementById('input-adspower-key')?.value.trim() || '';
        const res = await fetch(`/api/adspower/profiles?api_url=${encodeURIComponent(url)}&api_key=${encodeURIComponent(key)}`);
        const data = await res.json();
        if (data.success && data.profiles) {
            availableAdsPowerProfiles = data.profiles;
            if (populateSelect) {
                populateAdsPowerSelectDropdown(availableAdsPowerProfiles);
            }
        }
    } catch (err) {
        console.error('Fetch AdsPower profiles error:', err);
    }
}

function populateAdsPowerSelectDropdown(profiles) {
    const selectQuick = document.getElementById('select-acc-adspower-quick');
    if (!selectQuick) return;

    selectQuick.innerHTML = '<option value="">-- Chọn profile AdsPower có sẵn --</option>';
    profiles.forEach(p => {
        const opt = document.createElement('option');
        opt.value = p.user_id || p.serial_number;
        opt.textContent = `[#${p.serial_number}] ${p.name || 'Unnamed'} (${p.user_id})`;
        selectQuick.appendChild(opt);
    });
}

async function checkHmaIp(silent = false) {
    const badge = document.getElementById('hma-current-ip-badge');
    if (badge) badge.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> IP: Checking...';

    try {
        const res = await fetch('/api/hma/test_ip', { method: 'POST' });
        const data = await res.json();

        if (data.success && data.ip) {
            if (badge) {
                const countryTag = data.country ? ` (${data.country})` : '';
                badge.innerHTML = `<i class="fa-solid fa-globe text-success"></i> IP: ${data.ip}${countryTag}`;
            }
            if (!silent) {
                alert(`🌐 Thông tin IP hiện tại:\n- IP: ${data.ip}\n- Quốc gia: ${data.country || 'N/A'}\n- Thành phố: ${data.city || 'N/A'}\n- ISP: ${data.isp || 'N/A'}`);
            }
        } else {
            if (badge) badge.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> IP: Unknown';
        }
    } catch (err) {
        if (badge) badge.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> IP Error';
    }
}

async function testHmaChangeIp() {
    const cliPath = document.getElementById('input-hma-path')?.value.trim() || '';
    if (!confirm('Bạn có muốn thực hiện đổi IP ngẫu nhiên qua HMA VPN ngay bây giờ không?')) return;

    try {
        const res = await fetch('/api/hma/change_ip', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ cli_path: cliPath })
        });
        const data = await res.json();
        if (data.success) {
            await checkHmaIp(true);
            alert(`✅ ${data.message || 'Đã gửi lệnh đổi IP HMA VPN thành công!'}`);
        } else {
            alert(`❌ Lỗi: ${data.error || 'Không thể đổi IP'}`);
        }
    } catch (err) {
        alert('Lỗi kết nối: ' + err.message);
    }
}

async function disconnectHma() {
    const cliPath = document.getElementById('input-hma-path')?.value.trim() || '';
    if (!confirm('Ngắt kết nối HMA VPN?')) return;

    try {
        const res = await fetch('/api/hma/disconnect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ cli_path: cliPath })
        });
        const data = await res.json();
        if (data.success) {
            await checkHmaIp(true);
            alert('✅ Đã ngắt kết nối HMA VPN.');
        } else {
            alert(`❌ Lỗi: ${data.error || 'Không thể ngắt kết nối'}`);
        }
    } catch (err) {
        alert('Lỗi kết nối: ' + err.message);
    }
}

async function autoDetectHma() {
    try {
        const res = await fetch('/api/settings');
        const data = await res.json();
        const detected = data.hma_detected_path || '';
        if (detected) {
            document.getElementById('input-hma-path').value = detected;
            alert(`🔍 Đã tự động phát hiện HMA CLI tại:\n${detected}`);
        } else {
            alert('⚠️ Không tự động tìm thấy HMA CLI tại các vị trí mặc định. Vui lòng chọn thủ công tệp HMA.exe trên máy bạn.');
        }
    } catch (err) {
        alert('Lỗi khi phát hiện HMA: ' + err.message);
    }
}

async function pickLocalFolder() {
    try {
        const res = await fetch('/api/select_folder', { method: 'POST' });
        const data = await res.json();
        return data.folder_path || '';
    } catch (err) {
        return '';
    }
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
window.handleTogglePartPost = handleTogglePartPost;
window.handleSelectPartToPost = handleSelectPartToPost;
window.handleCopyCaptionForClip = handleCopyCaptionForClip;
window.handleAutoPostToTikTok = handleAutoPostToTikTok;
window.initSettingsManager = initSettingsManager;
window.fetchSettings = fetchSettings;
window.saveAllSettings = saveAllSettings;
window.testAdsPowerConnection = testAdsPowerConnection;
window.checkHmaIp = checkHmaIp;

/* ==========================================================================
   Auto-Pilot Pipeline Hub (All-in-One Automation & Nightly Scheduler)
   ========================================================================== */
let isAutopilotRunning = false;
let autopilotCancelRequested = false;
let pendingQueueCache = [];

function initAutoPilotHub() {
    const btnOpenModal = document.getElementById('btn-open-autopilot-modal');
    const btnCloseModal = document.getElementById('btn-close-autopilot-modal');
    const modal = document.getElementById('modal-autopilot-pipeline');
    const btnRefreshQueue = document.getElementById('btn-refresh-autopilot-queue');
    const btnStartModal = document.getElementById('btn-start-autopilot');
    const btnStopModal = document.getElementById('btn-stop-autopilot');
    const btnOpenN8nModal = document.getElementById('btn-open-n8n-tab');

    // Page Tab Elements
    const btnBannerOpen = document.getElementById('btn-banner-open-autopilot');
    const btnStartPage = document.getElementById('btn-page-start-autopilot');
    const btnStopPage = document.getElementById('btn-page-stop-autopilot');
    const btnRefreshPage = document.getElementById('btn-page-refresh-queue');
    const btnOpenN8nPage = document.getElementById('btn-page-open-n8n');

    // Header Button -> Open Modal
    if (btnOpenModal && modal) {
        btnOpenModal.addEventListener('click', () => {
            modal.classList.remove('hidden');
            loadAutopilotQueue();
        });
    }

    // Modal Close
    if (btnCloseModal && modal) {
        btnCloseModal.addEventListener('click', () => {
            if (isAutopilotRunning) {
                if (!confirm('Tiến trình Auto-Pilot đang chạy! Bạn có chắc muốn đóng cửa sổ? (Tiến trình vẫn tiếp tục chạy ngầm)')) {
                    return;
                }
            }
            modal.classList.add('hidden');
        });
    }

    // Banner Button in Posting Tracker -> Switch to Auto-Pilot Tab
    if (btnBannerOpen) {
        btnBannerOpen.addEventListener('click', () => {
            const tabBtn = document.getElementById('tab-btn-autopilot');
            if (tabBtn) {
                tabBtn.click();
            } else if (modal) {
                modal.classList.remove('hidden');
                loadAutopilotQueue();
            }
        });
    }

    // Refresh Queue
    if (btnRefreshQueue) btnRefreshQueue.addEventListener('click', loadAutopilotQueue);
    if (btnRefreshPage) btnRefreshPage.addEventListener('click', loadAutopilotQueue);

    // Open n8n Dashboard
    const openN8nHandler = () => window.open('http://localhost:5678', '_blank');
    if (btnOpenN8nModal) btnOpenN8nModal.addEventListener('click', openN8nHandler);
    if (btnOpenN8nPage) btnOpenN8nPage.addEventListener('click', openN8nHandler);

    // Start / Stop Pipeline
    if (btnStartModal) btnStartModal.addEventListener('click', startAutopilotPipeline);
    if (btnStartPage) btnStartPage.addEventListener('click', startAutopilotPipeline);
    if (btnStopModal) btnStopModal.addEventListener('click', stopAutopilotPipeline);
    if (btnStopPage) btnStopPage.addEventListener('click', stopAutopilotPipeline);

    // Pre-load on init
    loadAutopilotQueue();
}

async function loadAutopilotQueue() {
    const queueBadgeModal = document.getElementById('autopilot-queue-badge');
    const queuePreviewModal = document.getElementById('autopilot-queue-preview');
    const queueCountPage = document.getElementById('tab-autopilot-queue-count');
    const accountsCountPage = document.getElementById('tab-autopilot-accounts-count');
    const tableBodyPage = document.getElementById('tab-autopilot-table-body');

    if (queueBadgeModal) queueBadgeModal.textContent = 'Đang quét...';
    if (queuePreviewModal) queuePreviewModal.innerHTML = '<div style="color: var(--text-secondary); text-align: center; padding: 10px;">Đang tải danh sách clip chờ đăng...</div>';
    if (tableBodyPage) tableBodyPage.innerHTML = '<tr><td colspan="5" class="table-empty">Đang tải danh sách clip chờ đăng...</td></tr>';

    try {
        const res = await fetch('/api/n8n/pending_clips?only_current_target=true');
        const data = await res.json();
        if (data.success) {
            pendingQueueCache = data.items || [];
            const total = pendingQueueCache.length;

            // Unique accounts
            const uniqueAccs = new Set(pendingQueueCache.map(i => i.account_name));

            // Update Counts
            if (queueCountPage) queueCountPage.textContent = `${total} Clip`;
            if (accountsCountPage) accountsCountPage.textContent = `${uniqueAccs.size} Acc`;

            if (queueBadgeModal) {
                queueBadgeModal.textContent = `${total} clip sẵn sàng`;
                queueBadgeModal.className = total > 0 ? 'badge badge-primary' : 'badge badge-secondary';
            }

            // Populate Modal Preview
            if (queuePreviewModal) {
                if (total === 0) {
                    queuePreviewModal.innerHTML = '<div style="color: var(--text-secondary); padding: 8px; text-align: center;"><i class="fa-solid fa-circle-check text-success"></i> Tuyệt vời! Tất cả video đã được đăng tải hoặc không có clip nào chờ đăng.</div>';
                } else {
                    queuePreviewModal.innerHTML = pendingQueueCache.map((item, idx) => `
                        <div style="display: flex; justify-content: space-between; align-items: center; background: rgba(0,0,0,0.08); padding: 6px 10px; border-radius: 6px; border: 1px solid var(--border-color);">
                            <div style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 70%;">
                                <span style="font-weight: 700; color: var(--primary); font-size: 11px;">#${idx+1} [${escapeHtml(item.channel || '')}]</span>
                                <strong style="font-size: 12px; margin-left: 4px;">${escapeHtml(item.title || '')}</strong>
                                ${item.part_label ? `<span class="badge badge-info" style="font-size: 10px; margin-left: 4px;">${escapeHtml(item.part_label)}</span>` : ''}
                            </div>
                            <div style="font-size: 11px; color: var(--text-secondary);">
                                👤 @<strong>${escapeHtml(item.account_name || '')}</strong> (IP: ${escapeHtml(item.target_ip || 'US')})
                            </div>
                        </div>
                    `).join('');
                }
            }

            // Populate Full Page Table
            if (tableBodyPage) {
                if (total === 0) {
                    tableBodyPage.innerHTML = '<tr><td colspan="5" class="table-empty"><i class="fa-solid fa-circle-check text-success"></i> Tuyệt vời! Tất cả video đã được đăng tải hoặc không có clip nào chờ đăng.</td></tr>';
                } else {
                    tableBodyPage.innerHTML = pendingQueueCache.map((item, idx) => `
                        <tr>
                            <td style="text-align: center; font-weight: 700;">${idx+1}</td>
                            <td>
                                <div style="font-size: 11px; color: var(--primary); font-weight: 700;">${escapeHtml(item.channel || '')}</div>
                                <div style="font-weight: 700; font-size: 13px;">${escapeHtml(item.title || '')}</div>
                            </td>
                            <td>
                                ${item.part_label ? `<span class="badge badge-info">${escapeHtml(item.part_label)}</span>` : '<span class="text-muted">Full</span>'}
                            </td>
                            <td>
                                <span style="font-weight: 800; color: var(--accent);">@${escapeHtml(item.account_name || '')}</span>
                            </td>
                            <td style="text-align: center;">
                                <span class="badge badge-primary">${escapeHtml(item.target_ip || 'US')}</span>
                            </td>
                        </tr>
                    `).join('');
                }
            }
        }
    } catch (err) {
        if (queueBadgeModal) queueBadgeModal.textContent = 'Lỗi quét';
        if (queuePreviewModal) queuePreviewModal.innerHTML = `<div style="color: #ef4444; padding: 8px;">Lỗi kết nối: ${err.message}</div>`;
        if (tableBodyPage) tableBodyPage.innerHTML = `<tr><td colspan="5" style="color: #ef4444; text-align: center;">Lỗi kết nối: ${err.message}</td></tr>`;
    }
}

function appendAutopilotLog(msg, type = 'info') {
    const timeStr = new Date().toLocaleTimeString();
    const containers = [
        document.getElementById('autopilot-logs'),
        document.getElementById('tab-autopilot-logs')
    ];

    containers.forEach(container => {
        if (!container) return;
        const logLine = document.createElement('div');
        logLine.className = 'log-line';
        if (type === 'success') logLine.style.color = '#22c55e';
        else if (type === 'error') logLine.style.color = '#ef4444';
        else if (type === 'warn') logLine.style.color = '#f59e0b';
        else logLine.style.color = '#60a5fa';

        logLine.textContent = `[${timeStr}] ${msg}`;
        container.appendChild(logLine);
        container.scrollTop = container.scrollHeight;
    });
}

async function startAutopilotPipeline() {
    if (pendingQueueCache.length === 0) {
        await loadAutopilotQueue();
        if (pendingQueueCache.length === 0) {
            alert('Không có clip nào trong hàng đợi chờ xuất bản!');
            return;
        }
    }

    const optShutdown = (document.getElementById('autopilot-opt-shutdown')?.checked) ||
                        (document.getElementById('tab-opt-shutdown')?.checked) || false;

    isAutopilotRunning = true;
    autopilotCancelRequested = false;

    const execBoxModal = document.getElementById('autopilot-execution-box');
    const btnStartModal = document.getElementById('btn-start-autopilot');
    const btnStopModal = document.getElementById('btn-stop-autopilot');
    const btnStartPage = document.getElementById('btn-page-start-autopilot');
    const btnStopPage = document.getElementById('btn-page-stop-autopilot');
    const statusBadgePage = document.getElementById('tab-autopilot-status-badge');

    if (execBoxModal) execBoxModal.classList.remove('hidden');
    if (btnStartModal) btnStartModal.classList.add('hidden');
    if (btnStopModal) btnStopModal.classList.remove('hidden');
    if (btnStartPage) btnStartPage.classList.add('hidden');
    if (btnStopPage) btnStopPage.classList.remove('hidden');
    if (statusBadgePage) {
        statusBadgePage.textContent = 'Đang chạy...';
        statusBadgePage.className = 'badge badge-primary';
    }

    // Clear logs
    const logsModal = document.getElementById('autopilot-logs');
    const logsPage = document.getElementById('tab-autopilot-logs');
    if (logsModal) logsModal.innerHTML = '';
    if (logsPage) logsPage.innerHTML = '';

    appendAutopilotLog(`🚀 Bắt đầu quy trình Auto-Pilot Pipeline (${pendingQueueCache.length} clip)...`, 'info');

    const total = pendingQueueCache.length;
    let successCount = 0;
    let failCount = 0;

    for (let i = 0; i < total; i++) {
        if (autopilotCancelRequested) {
            appendAutopilotLog('⚠️ Tiến trình đã bị người dùng dừng lại!', 'warn');
            break;
        }

        const item = pendingQueueCache[i];
        const clipTitle = `${item.title} ${item.part_label ? `(${item.part_label})` : ''}`.trim();
        const percent = Math.round((i / total) * 100);

        // Update progress UI on both Modal & Page
        const progressBars = [document.getElementById('autopilot-progress-bar'), document.getElementById('tab-autopilot-progress-bar')];
        const percentTexts = [document.getElementById('autopilot-progress-percent'), document.getElementById('tab-autopilot-progress-percent')];
        const currentTasks = [document.getElementById('autopilot-current-task'), document.getElementById('tab-autopilot-current-task')];

        progressBars.forEach(b => { if (b) b.style.width = `${percent}%`; });
        percentTexts.forEach(p => { if (p) p.textContent = `${percent}%`; });
        currentTasks.forEach(t => { if (t) t.textContent = `[${i+1}/${total}] Đang đăng: ${clipTitle} (@${item.account_name})`; });

        appendAutopilotLog(`▶️ [${i+1}/${total}] Chuẩn bị đăng: "${clipTitle}" cho tài khoản @${item.account_name}`, 'info');

        try {
            const payload = {
                account_name: item.account_name,
                clip_key: item.clip_key,
                channel: item.channel,
                title: item.title,
                video_file: item.video_file,
                part_label: item.part_label,
                auto_submit: true
            };

            appendAutopilotLog(`   ⚡ Đang kết nối AdsPower & TikTok Studio...`, 'info');
            const res = await fetch('/api/publishing/post_to_tiktok', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const data = await res.json();
            if (data.success) {
                successCount++;
                appendAutopilotLog(`   🎉 ĐĂNG THÀNH CÔNG: "${clipTitle}"!`, 'success');
            } else {
                failCount++;
                appendAutopilotLog(`   ❌ Thất bại: ${data.error || 'Lỗi không xác định'}`, 'error');
            }
        } catch (err) {
            failCount++;
            appendAutopilotLog(`   ❌ Lỗi kết nối: ${err.message}`, 'error');
        }

        // Nghỉ ngắn 4 giây giữa các clip
        if (i < total - 1 && !autopilotCancelRequested) {
            appendAutopilotLog('   ⏳ Chờ 4 giây trước clip tiếp theo...', 'info');
            await new Promise(r => setTimeout(r, 4000));
        }
    }

    const progressBars = [document.getElementById('autopilot-progress-bar'), document.getElementById('tab-autopilot-progress-bar')];
    const percentTexts = [document.getElementById('autopilot-progress-percent'), document.getElementById('tab-autopilot-progress-percent')];
    const currentTasks = [document.getElementById('autopilot-current-task'), document.getElementById('tab-autopilot-current-task')];

    progressBars.forEach(b => { if (b) b.style.width = '100%'; });
    percentTexts.forEach(p => { if (p) p.textContent = '100%'; });
    currentTasks.forEach(t => { if (t) t.textContent = 'Hoàn thành toàn bộ Pipeline!'; });

    appendAutopilotLog(`🏁 HOÀN TẤT PIPELINE! Thành công: ${successCount} | Thất bại: ${failCount}`, successCount > 0 ? 'success' : 'warn');

    if (statusBadgePage) {
        statusBadgePage.textContent = 'Đã hoàn thành';
        statusBadgePage.className = 'badge badge-success';
    }

    // Nếu chọn tự động tắt máy
    if (optShutdown && !autopilotCancelRequested) {
        appendAutopilotLog('💤 Đang kích hoạt chế độ hẹn giờ tự động tắt máy tính sau 15 phút...', 'warn');
        try {
            await fetch('/api/system/shutdown', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ delay_seconds: 900 })
            });
            appendAutopilotLog('✅ Đã hẹn giờ Shutdown máy tính thành công. Bạn có thể yên tâm đi ngủ!', 'success');
        } catch (e) {
            appendAutopilotLog(`⚠️ Lỗi hẹn giờ tắt máy: ${e.message}`, 'error');
        }
    }

    // Refresh UI matrix
    if (typeof fetchPublishingMatrix === 'function') {
        fetchPublishingMatrix();
    }
    await loadAutopilotQueue();

    isAutopilotRunning = false;
    if (btnStartModal) btnStartModal.classList.remove('hidden');
    if (btnStopModal) btnStopModal.classList.add('hidden');
    if (btnStartPage) btnStartPage.classList.remove('hidden');
    if (btnStopPage) btnStopPage.classList.add('hidden');
}

async function stopAutopilotPipeline() {
    autopilotCancelRequested = true;
    appendAutopilotLog('🛑 Đang gửi tín hiệu dừng pipeline...', 'warn');
    try {
        await fetch('/api/pipeline/stop_batch', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
        await fetch('/api/system/cancel_shutdown', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
    } catch (e) {}
}

window.initAutoPilotHub = initAutoPilotHub;
window.loadAutopilotQueue = loadAutopilotQueue;
window.startAutopilotPipeline = startAutopilotPipeline;
window.stopAutopilotPipeline = stopAutopilotPipeline;



