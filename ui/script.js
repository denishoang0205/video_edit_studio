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
    initDashboardSubtabs();
    initTheme();
    initLivePreview();
    setupEventListeners();
    initSettingsManager();
    initAccountsManager();
    initPublishingTracker();
    initAutoPilotHub();
    initDownloadVideoPipeline();
    initTikTokAnalyticsEngine();
    initLogsControls();
    checkAndPollProgress();
});

/* ==========================================================================
   Utility: HTML & Attribute Escaping, Debounce & Modern Floating Toast
   ========================================================================== */
function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}
window.escapeHtml = escapeHtml;

function escapeAttr(str) {
    if (str === null || str === undefined) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}
window.escapeAttr = escapeAttr;

function debounce(fn, delay = 120) {
    let timer = null;
    return function(...args) {
        clearTimeout(timer);
        timer = setTimeout(() => fn.apply(this, args), delay);
    };
}

function showToast(message, type = 'info', duration = 3000) {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast-message toast-${type}`;
    
    let iconClass = 'fa-solid fa-circle-info';
    if (type === 'success') iconClass = 'fa-solid fa-circle-check text-success';
    else if (type === 'error') iconClass = 'fa-solid fa-circle-exclamation text-danger';
    else if (type === 'warning') iconClass = 'fa-solid fa-triangle-exclamation text-warning';

    toast.innerHTML = `
        <i class="${iconClass}" style="font-size: 16px;"></i>
        <div style="flex: 1; line-height: 1.4;">${escapeHtml(message)}</div>
    `;

    container.appendChild(toast);

    setTimeout(() => {
        toast.classList.add('toast-hide');
        setTimeout(() => {
            if (toast.parentNode) toast.parentNode.removeChild(toast);
        }, 220);
    }, duration);
}
window.showToast = showToast;

/* ==========================================================================
   1. Tab Navigation & Theme Engine
   ========================================================================== */
const TAB_HEADER_METADATA = {
    'tab-dashboard': {
        title: 'Dashboard',
        subtitle: 'Tổng quan hệ thống, thống kê video tải về và tiến độ biên tập toàn diện'
    },
    'tab-download': {
        title: 'Download Video',
        subtitle: 'Quét và tải video/shorts tự động từ danh sách kênh YouTube mục tiêu'
    },
    'tab-studio': {
        title: 'Editor Studio',
        subtitle: 'Cấu hình thông số render, Live Preview Canvas trực quan và chọn video biên tập'
    },
    'tab-outputs': {
        title: 'Finished Library',
        subtitle: 'Thư viện video thành phẩm, sắp xếp thông minh theo trạng thái tải lên TikTok'
    },
    'tab-autopilot': {
        title: 'Automation Pipeline',
        subtitle: 'Trung tâm tự động hóa toàn diện từ Download ➔ Edit ➔ Render ➔ Upload TikTok'
    },
    'tab-publishing': {
        title: 'Posting Tracker',
        subtitle: 'Ma trận phân phối và theo dõi trạng thái xuất bản clip lên tài khoản TikTok'
    },
    'tab-tiktok': {
        title: 'Account Management',
        subtitle: 'Quản lý tài khoản TikTok, AdsPower Browser profiles và cấu hình đăng video'
    },
    'tab-channels': {
        title: 'YouTube Channels',
        subtitle: 'Danh sách các kênh YouTube nguồn và phân loại nội dung mục tiêu'
    },
    'tab-config': {
        title: 'Settings',
        subtitle: 'Cài đặt đường dẫn thư mục, AdsPower Local API, HMA VPN, Gemini AI và Telegram Bot'
    },
    'tab-logs': {
        title: 'Logs & Console',
        subtitle: 'Bảng điều khiển tiến trình thời gian thực, tiến độ render video và lịch sử terminal console'
    }
};

function initTabs() {
    const tabLinks = document.querySelectorAll('.tab-link');
    const tabContents = document.querySelectorAll('.tab-content');
    const titleEl = document.getElementById('current-tab-title');
    const subEl = document.getElementById('current-tab-subtitle');
    const mainContent = document.querySelector('.app-main-content');

    tabLinks.forEach(link => {
        link.addEventListener('click', () => {
            const targetTab = link.dataset.tab;
            if (!targetTab) return;
            
            // Toggle active classes instantaneously
            tabLinks.forEach(l => l.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));
            
            link.classList.add('active');
            const targetEl = document.getElementById(targetTab);
            if (targetEl) {
                targetEl.classList.add('active');
            }

            // Cập nhật Tiêu đề và Mô tả trên Top Bar
            const meta = TAB_HEADER_METADATA[targetTab];
            if (meta) {
                if (titleEl) titleEl.textContent = meta.title;
                if (subEl) subEl.textContent = meta.subtitle;
            }

            // Cuộn trang lên đầu tức thì không bị giật lag
            if (mainContent) {
                mainContent.scrollTop = 0;
            }

            if (targetTab === 'tab-publishing') {
                fetchPublishingMatrix();
            } else if (targetTab === 'tab-autopilot') {
                loadAutopilotQueue();
            } else if (targetTab === 'tab-download') {
                onDownloadTabActivated();
            }
        });
    });
}

function initDashboardSubtabs() {
    const btnWebapp = document.getElementById('btn-subtab-webapp');
    const btnTiktok = document.getElementById('btn-subtab-tiktok');
    const viewWebapp = document.getElementById('subtab-webapp');
    const viewTiktok = document.getElementById('subtab-tiktok');

    if (!btnWebapp || !btnTiktok || !viewWebapp || !viewTiktok) return;

    btnWebapp.addEventListener('click', () => {
        btnWebapp.classList.add('active');
        btnTiktok.classList.remove('active');
        viewWebapp.style.display = 'block';
        viewTiktok.style.display = 'none';
    });

    btnTiktok.addEventListener('click', () => {
        btnTiktok.classList.add('active');
        btnWebapp.classList.remove('active');
        viewWebapp.style.display = 'none';
        viewTiktok.style.display = 'block';
        if (typeof loadAnalyticsData === 'function') {
            loadAnalyticsData();
        }
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
    const effectHFlip = document.getElementById('effect-hflip');
    const effectColorBoost = document.getElementById('effect-color-boost');
    const canvasFgVideo = document.getElementById('canvas-fg-video');
    const canvasFlipIndicator = document.getElementById('canvas-flip-indicator');
    const canvasHdrIndicator = document.getElementById('canvas-hdr-indicator');
    const bannerPosition = document.getElementById('banner-position');
    const splitModeSelect = document.getElementById('split-mode');
    const canvasSplitTagText = document.getElementById('canvas-split-tag-text');

    // Ratio Switcher
    ratioInputs.forEach(input => {
        input.addEventListener('change', (e) => {
            document.querySelectorAll('.ratio-card').forEach(c => c.classList.remove('active'));
            e.target.closest('.ratio-card').classList.add('active');
            
            const val = e.target.value;
            if (mockupCanvas) mockupCanvas.className = `mockup-canvas ratio-${val.replace(':', '-')}-canvas`;
            if (previewRatioLabel) previewRatioLabel.textContent = `${val} Canvas`;
        });
    });

    // Box Style
    if (boxStyleSelect && canvasBanner) {
        boxStyleSelect.addEventListener('change', (e) => {
            canvasBanner.className = `canvas-banner banner-${e.target.value}`;
        });
    }

    // Dynamic Font System
    const fontMap = {
        "Poppins-Bold": "Poppins, sans-serif",
        "Montserrat-Bold": "Montserrat, sans-serif",
        "Arial-Bold": "Arial, sans-serif",
        "Arial": "Arial, sans-serif",
        "SegoeUI-Bold": "'Segoe UI', sans-serif",
        "Tahoma-Bold": "Tahoma, sans-serif",
        "Impact": "Impact, sans-serif",
        "BeVietnamPro-Bold": "'Be Vietnam Pro', sans-serif"
    };

    const loadDynamicFonts = async () => {
        if (!fontSelect) return;
        try {
            const res = await fetch('/api/assets/fonts');
            if (!res.ok) return;
            const data = await res.json();
            if (data && data.fonts && Array.isArray(data.fonts)) {
                const currentVal = fontSelect.value;
                const existingValues = new Set(Array.from(fontSelect.options).map(opt => opt.value));
                
                data.fonts.forEach(f => {
                    if (!existingValues.has(f.id)) {
                        const opt = document.createElement('option');
                        opt.value = f.id;
                        opt.textContent = f.name + (f.is_custom ? " (Assets)" : "");
                        fontSelect.appendChild(opt);
                        existingValues.add(f.id);
                    }
                    if (!fontMap[f.id]) {
                        fontMap[f.id] = `"${f.name}", "${f.id}", sans-serif`;
                    }
                });
                if (currentVal) fontSelect.value = currentVal;
            }
        } catch (e) {
            console.warn("Could not load dynamic fonts:", e);
        }
    };
    loadDynamicFonts();

    const updateFontFamily = () => {
        if (!fontSelect || !canvasBanner) return;
        const family = fontMap[fontSelect.value] || `"${fontSelect.value}", sans-serif`;
        canvasBanner.style.fontFamily = family;
        if (canvasBannerText) {
            canvasBannerText.style.fontFamily = family;
        }
    };
    if (fontSelect) {
        fontSelect.addEventListener('change', updateFontFamily);
    }

    // Font Size
    if (fontSizeInput) {
        fontSizeInput.addEventListener('input', (e) => {
            if (fontSizeVal) fontSizeVal.textContent = `${e.target.value}px`;
            // Scale proportionally in miniature canvas
            const scaledSize = Math.max(9, Math.round(e.target.value * 0.22));
            if (canvasBanner) canvasBanner.style.fontSize = `${scaledSize}px`;
        });
    }

    // Text Live Sync
    if (previewTextInput) {
        previewTextInput.addEventListener('input', (e) => {
            if (canvasBannerText) {
                canvasBannerText.textContent = e.target.value.toUpperCase() || "SAMPLE VIDEO TITLE";
            }
        });
    }

    // Blur Background Toggle
    if (effectBlur && canvasBgBlur) {
        effectBlur.addEventListener('change', (e) => {
            canvasBgBlur.style.opacity = e.target.checked ? '0.85' : '0.1';
            const blurBadge = document.querySelector('.badge-blur-status');
            if (blurBadge) {
                blurBadge.style.opacity = e.target.checked ? '1' : '0.4';
            }
        });
    }

    // Horizontal Flip (Mirror) Toggle with Reactive Canvas
    if (effectHFlip && canvasFgVideo) {
        effectHFlip.addEventListener('change', (e) => {
            if (e.target.checked) {
                canvasFgVideo.classList.add('is-flipped');
                if (canvasFlipIndicator) canvasFlipIndicator.classList.remove('hidden');
            } else {
                canvasFgVideo.classList.remove('is-flipped');
                if (canvasFlipIndicator) canvasFlipIndicator.classList.add('hidden');
            }
        });
    }

    // Color & Contrast Boost (HDR Vibe) Toggle with Reactive Canvas
    if (effectColorBoost && canvasFgVideo) {
        effectColorBoost.addEventListener('change', (e) => {
            if (e.target.checked) {
                canvasFgVideo.classList.add('is-color-boosted');
                if (canvasHdrIndicator) canvasHdrIndicator.classList.remove('hidden');
            } else {
                canvasFgVideo.classList.remove('is-color-boosted');
                if (canvasHdrIndicator) canvasHdrIndicator.classList.add('hidden');
            }
        });
    }

    // Banner Position
    if (bannerPosition && canvasBanner) {
        bannerPosition.addEventListener('change', (e) => {
            const pos = e.target.value;
            if (pos === 'top') {
                canvasBanner.style.top = '16px';
                canvasBanner.style.bottom = 'auto';
            } else if (pos === 'center') {
                canvasBanner.style.top = '40%';
                canvasBanner.style.bottom = 'auto';
            } else if (pos === 'bottom') {
                canvasBanner.style.top = 'auto';
                canvasBanner.style.bottom = '16px';
            }
        });
    }

    // Split Mode Badge Sync
    const splitLabelMap = {
        'auto-highlight-45s': 'Auto Climax 45s',
        'auto-highlight-60s': 'Auto Climax 60s',
        'auto-highlight-30s': 'Auto Climax 30s',
        'fixed-3': 'Fixed 3 Parts',
        'fixed-6': 'Fixed 6 Parts',
        'no-split': 'Full Video (No Split)'
    };
    if (splitModeSelect && canvasSplitTagText) {
        splitModeSelect.addEventListener('change', (e) => {
            canvasSplitTagText.textContent = splitLabelMap[e.target.value] || e.target.value;
        });
    }

    // Hàm đồng bộ tất cả các thuộc tính xem trước trên canvas khi tải trang
    const syncAllPreview = () => {
        updateFontFamily();
        
        // Đồng bộ cỡ chữ
        if (fontSizeInput && fontSizeVal) {
            fontSizeVal.textContent = `${fontSizeInput.value}px`;
            const scaledSize = Math.max(9, Math.round(fontSizeInput.value * 0.22));
            if (canvasBanner) canvasBanner.style.fontSize = `${scaledSize}px`;
        }
        
        // Đồng bộ kiểu hộp banner
        if (boxStyleSelect && canvasBanner) {
            canvasBanner.className = `canvas-banner banner-${boxStyleSelect.value}`;
        }
        
        // Đồng bộ văn bản mẫu
        if (previewTextInput && canvasBannerText) {
            canvasBannerText.textContent = previewTextInput.value.toUpperCase() || "SAMPLE VIDEO TITLE";
        }
        
        // Đồng bộ độ mờ nền
        if (effectBlur && canvasBgBlur) {
            canvasBgBlur.style.opacity = effectBlur.checked ? '0.85' : '0.1';
        }

        // Đồng bộ Flip
        if (effectHFlip && canvasFgVideo) {
            if (effectHFlip.checked) {
                canvasFgVideo.classList.add('is-flipped');
                if (canvasFlipIndicator) canvasFlipIndicator.classList.remove('hidden');
            } else {
                canvasFgVideo.classList.remove('is-flipped');
                if (canvasFlipIndicator) canvasFlipIndicator.classList.add('hidden');
            }
        }

        // Đồng bộ Color Boost
        if (effectColorBoost && canvasFgVideo) {
            if (effectColorBoost.checked) {
                canvasFgVideo.classList.add('is-color-boosted');
                if (canvasHdrIndicator) canvasHdrIndicator.classList.remove('hidden');
            } else {
                canvasFgVideo.classList.remove('is-color-boosted');
                if (canvasHdrIndicator) canvasHdrIndicator.classList.add('hidden');
            }
        }
        
        // Đồng bộ vị trí banner
        if (bannerPosition && canvasBanner) {
            const pos = bannerPosition.value;
            if (pos === 'top') {
                canvasBanner.style.top = '16px';
                canvasBanner.style.bottom = 'auto';
            } else if (pos === 'center') {
                canvasBanner.style.top = '40%';
                canvasBanner.style.bottom = 'auto';
            } else if (pos === 'bottom') {
                canvasBanner.style.top = 'auto';
                canvasBanner.style.bottom = '16px';
            }
        }

        // Đồng bộ Split Mode
        if (splitModeSelect && canvasSplitTagText) {
            canvasSplitTagText.textContent = splitLabelMap[splitModeSelect.value] || splitModeSelect.value;
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
    const btnSelectAllUnedited = document.getElementById('btn-select-all-unedited-btn');
    const btnDeselectAll = document.getElementById('btn-deselect-all-btn');
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
            const itemRow = cb.closest('.video-tree-item');
            const folderGroup = cb.closest('.folder-group');
            const isVisible = itemRow && itemRow.style.display !== 'none' && folderGroup && folderGroup.style.display !== 'none';
            // Chỉ áp dụng chọn/bỏ chọn cho các video chưa edit đang hiển thị
            if (!isEdited && isVisible) {
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

    if (btnSelectAllUnedited) {
        btnSelectAllUnedited.addEventListener('click', () => {
            const checkboxes = document.querySelectorAll('.video-checkbox');
            checkboxes.forEach(cb => {
                const isEdited = cb.dataset.edited === 'true';
                const itemRow = cb.closest('.video-tree-item');
                const folderGroup = cb.closest('.folder-group');
                const isVisible = itemRow && itemRow.style.display !== 'none' && folderGroup && folderGroup.style.display !== 'none';
                if (!isEdited && isVisible) {
                    cb.checked = true;
                    selectedVideos.add(cb.dataset.path);
                }
            });
            if (chkSelectAll) chkSelectAll.checked = true;
            updateSelectedCount();
        });
    }

    if (btnDeselectAll) {
        btnDeselectAll.addEventListener('click', () => {
            const checkboxes = document.querySelectorAll('.video-checkbox');
            checkboxes.forEach(cb => {
                cb.checked = false;
            });
            selectedVideos.clear();
            if (chkSelectAll) chkSelectAll.checked = false;
            updateSelectedCount();
        });
    }

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

    // Finished Library Filter Tabs & Live Search
    const finishedFilterBtns = document.querySelectorAll('.finished-filter-btn');
    finishedFilterBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            finishedFilterBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentFinishedFilter = btn.dataset.filter;
            renderFinishedLibrary();
        });
    });

    const inputSearchFinished = document.getElementById('input-search-finished');
    if (inputSearchFinished) {
        const debouncedFinishedSearch = debounce(() => {
            renderFinishedLibrary();
        }, 100);

        inputSearchFinished.addEventListener('input', (e) => {
            currentFinishedSearch = e.target.value.trim().toLowerCase();
            debouncedFinishedSearch();
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
    const fragment = document.createDocumentFragment();
    let totalVideosAcrossFolders = 0;

    folders.forEach(folder => {
        const totalVids = folder.videos ? folder.videos.length : 0;
        totalVideosAcrossFolders += totalVids;
        const editedVids = folder.videos ? folder.videos.filter(v => v.edited).length : 0;
        const uneditedVids = totalVids - editedVids;

        const folderEl = document.createElement('div');
        folderEl.className = 'folder-group is-collapsed';
        folderEl.dataset.folderName = folder.name;

        folderEl.innerHTML = `
            <div class="folder-header" title="Nhấn để mở rộng / thu gọn danh sách video kênh ${escapeHtml(folder.name)}">
                <div class="folder-left">
                    <i class="fa-solid fa-chevron-down folder-chevron"></i>
                    <i class="fa-solid fa-folder folder-icon"></i>
                    <span class="folder-name-text">${escapeHtml(folder.name)}</span>
                    <span class="folder-video-count-chip">${totalVids} video</span>
                </div>
                <div class="folder-right">
                    <button type="button" class="btn-select-folder-all" title="Chọn / Bỏ chọn toàn bộ video chưa edit trong kênh ${escapeAttr(folder.name)}">
                        <i class="fa-solid fa-check"></i> Chọn Kênh
                    </button>
                    <span class="badge folder-count-badge ${editedVids === totalVids && totalVids > 0 ? 'badge-success' : (uneditedVids > 0 ? 'badge-warning' : 'badge-info')}">
                        ${editedVids}/${totalVids} Đã edit
                    </span>
                </div>
            </div>
            <div class="folder-items-list"></div>
        `;

        const btnSelectFolder = folderEl.querySelector('.btn-select-folder-all');
        if (btnSelectFolder) {
            btnSelectFolder.addEventListener('click', (e) => {
                e.stopPropagation();
                const uneditedCheckboxes = Array.from(folderEl.querySelectorAll('.video-tree-item.is-unedited .video-checkbox'))
                    .filter(cb => cb.closest('.video-tree-item').style.display !== 'none');
                
                if (uneditedCheckboxes.length === 0) return;
                let allChecked = uneditedCheckboxes.every(cb => cb.checked);
                uneditedCheckboxes.forEach(cb => {
                    cb.checked = !allChecked;
                    if (!allChecked) {
                        selectedVideos.add(cb.dataset.path);
                    } else {
                        selectedVideos.delete(cb.dataset.path);
                    }
                });
                updateSelectedCount();
            });
        }

        const listEl = folderEl.querySelector('.folder-items-list');

        (folder.videos || []).forEach(video => {
            const itemEl = document.createElement('div');
            itemEl.className = `video-tree-item ${video.edited ? 'is-edited' : 'is-unedited'}`;
            itemEl.dataset.videoTitle = (video.title || '').toLowerCase();
            itemEl.dataset.channelName = (folder.name || '').toLowerCase();

            const durationFormatted = video.duration_str || '0:00';
            const badgeHtml = video.edited 
                ? '<span class="badge-status edited"><i class="fa-solid fa-check"></i> Đã edit</span>'
                : '<span class="badge-status unedited"><i class="fa-regular fa-circle"></i> Chưa edit</span>';

            itemEl.innerHTML = `
                <div class="video-item-left">
                    <label class="custom-checkbox">
                        <input type="checkbox" class="video-checkbox" data-path="${escapeAttr(video.path)}" data-title="${escapeAttr(video.title)}" data-edited="${video.edited}" data-channel="${escapeAttr(folder.name)}">
                        <span class="checkmark"></span>
                    </label>
                    <i class="fa-solid fa-play-circle video-row-icon"></i>
                    <span class="video-title-truncate" title="${escapeAttr(video.title)}">${escapeHtml(video.title)}</span>
                </div>
                <div class="video-item-right">
                    <span class="video-duration-badge" title="Thời lượng video: ${durationFormatted}">
                        <i class="fa-regular fa-clock"></i> ${durationFormatted}
                    </span>
                    ${badgeHtml}
                </div>
            `;

            // Click row to preview title live
            itemEl.addEventListener('click', (e) => {
                if (e.target.tagName === 'INPUT' || e.target.closest('.custom-checkbox')) return;
                document.querySelectorAll('.video-tree-item').forEach(el => el.classList.remove('is-preview-active'));
                itemEl.classList.add('is-preview-active');
                const sampleInput = document.getElementById('preview-text-input');
                const canvasBannerText = document.getElementById('canvas-banner-text');
                if (sampleInput) sampleInput.value = video.title;
                if (canvasBannerText) canvasBannerText.textContent = video.title.toUpperCase();
            });

            // Checkbox event
            const cb = itemEl.querySelector('.video-checkbox');
            cb.addEventListener('change', async (e) => {
                if (e.target.checked) {
                    if (video.edited) {
                        if (video.is_finished_only) {
                            showToast(`Video "${video.title}" đã được xuất thành phẩm hoàn tất!`, 'info');
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
                                    const statusWrapper = itemEl.querySelector('.video-item-right');
                                    if (statusWrapper) {
                                        statusWrapper.innerHTML = `
                                            <span class="video-duration-badge" title="Thời lượng video: ${durationFormatted}">
                                                <i class="fa-regular fa-clock"></i> ${durationFormatted}
                                            </span>
                                            <span class="badge-status unedited"><i class="fa-regular fa-circle"></i> Chưa edit</span>
                                        `;
                                    }
                                    fetchResults();
                                    selectedVideos.add(video.path);
                                    document.getElementById('preview-text-input').value = video.title;
                                    document.getElementById('canvas-banner-text').textContent = video.title.toUpperCase();
                                    updateSelectedCount();
                                    applyVideoTreeFilters();
                                    showToast(`Đã xóa bản thành phẩm cũ của "${video.title}"`, 'success');
                                    return;
                                }
                            } catch (err) {
                                showToast('Lỗi khi xóa bản thành phẩm cũ: ' + err.message, 'error');
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
            if (e.target.tagName === 'INPUT' || e.target.closest('.custom-checkbox') || e.target.closest('.btn-select-folder-all')) return;
            folderEl.classList.toggle('is-collapsed');
            const icon = folderEl.querySelector('.folder-icon');
            if (icon) {
                icon.className = folderEl.classList.contains('is-collapsed') 
                    ? 'fa-solid fa-folder folder-icon' 
                    : 'fa-solid fa-folder-open folder-icon';
            }
        });

        fragment.appendChild(folderEl);
    });

    container.appendChild(fragment);

    if (totalBadge) totalBadge.textContent = `${totalVideosAcrossFolders} Video`;
    
    // Apply current filter & search
    applyVideoTreeFilters();
    initExplorerControls();
}

function updateExplorerStats(folders) {
    let totalVideos = 0;
    (folders || []).forEach(f => totalVideos += (f.videos || []).length);
    const badge = document.getElementById('explorer-total-badge');
    if (badge) badge.textContent = `${totalVideos} Video`;
    const selBadge = document.getElementById('selected-count-badge');
    if (selBadge) selBadge.textContent = selectedVideos.size;
}

function filterVideoTree(filter) {
    currentVideoTreeFilter = filter;
    applyVideoTreeFilters();
}

function applyVideoTreeFilters() {
    const filter = currentVideoTreeFilter;
    const search = currentVideoTreeSearch.trim().toLowerCase();
    const folderGroups = document.querySelectorAll('.folder-group');
    let totalVisibleVideos = 0;

    folderGroups.forEach(folderEl => {
        const items = folderEl.querySelectorAll('.video-tree-item');
        const countBadge = folderEl.querySelector('.folder-count-badge');
        const folderIcon = folderEl.querySelector('.folder-icon');
        let visibleCountInFolder = 0;
        let totalUneditedInFolder = 0;
        let totalEditedInFolder = 0;

        items.forEach(item => {
            const isUnedited = item.classList.contains('is-unedited');
            const isEdited = item.classList.contains('is-edited');
            if (isUnedited) totalUneditedInFolder++;
            if (isEdited) totalEditedInFolder++;

            let matchesStatus = true;
            if (filter === 'unedited') {
                matchesStatus = isUnedited;
            } else if (filter === 'edited') {
                matchesStatus = isEdited;
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
                totalVisibleVideos++;
            } else {
                item.style.display = 'none';
            }
        });

        // Ẩn kênh nếu không có video nào khớp với filter và search
        if (visibleCountInFolder > 0) {
            folderEl.style.display = 'block';

            // Khi chọn filter Unedited hoặc Edited hoặc đang search: Tự động mở rộng kênh để người dùng nhìn thấy ngay danh sách video!
            if (filter === 'unedited' || filter === 'edited' || search) {
                folderEl.classList.remove('is-collapsed');
                if (folderIcon) folderIcon.className = 'fa-solid fa-folder-open folder-icon';
            }

            if (countBadge) {
                if (filter === 'unedited') {
                    countBadge.textContent = `${visibleCountInFolder} Chưa edit`;
                    countBadge.className = 'badge folder-count-badge badge-warning';
                } else if (filter === 'edited') {
                    countBadge.textContent = `${visibleCountInFolder} Đã edit`;
                    countBadge.className = 'badge folder-count-badge badge-success';
                } else {
                    countBadge.textContent = `${totalEditedInFolder}/${items.length} Đã edit`;
                    countBadge.className = `badge folder-count-badge ${totalEditedInFolder === items.length && items.length > 0 ? 'badge-success' : (totalUneditedInFolder > 0 ? 'badge-warning' : 'badge-info')}`;
                }
            }
        } else {
            folderEl.style.display = 'none';
        }
    });

    const totalBadge = document.getElementById('explorer-total-badge');
    if (totalBadge) {
        totalBadge.textContent = `${totalVisibleVideos} Video`;
    }
}

let explorerControlsInitialized = false;
function initExplorerControls() {
    if (explorerControlsInitialized) return;
    explorerControlsInitialized = true;

    // 1. Search Box input & clear
    const searchInput = document.getElementById('input-explorer-search');
    const clearBtn = document.getElementById('btn-clear-explorer-search');

    if (searchInput) {
        const debouncedExplorerSearch = debounce(() => {
            applyVideoTreeFilters();
        }, 100);

        searchInput.addEventListener('input', (e) => {
            currentVideoTreeSearch = e.target.value;
            if (clearBtn) {
                if (currentVideoTreeSearch) clearBtn.classList.remove('hidden');
                else clearBtn.classList.add('hidden');
            }
            debouncedExplorerSearch();
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

    // 2. Toggle Collapse / Expand All Folders
    const btnToggleAll = document.getElementById('btn-toggle-all-folders');
    if (btnToggleAll) {
        btnToggleAll.addEventListener('click', () => {
            const folders = document.querySelectorAll('.folder-group');
            const anyExpanded = Array.from(folders).some(f => !f.classList.contains('is-collapsed') && f.style.display !== 'none');
            const shouldCollapse = anyExpanded;

            folders.forEach(f => {
                const icon = f.querySelector('.folder-icon');
                if (shouldCollapse) {
                    f.classList.add('is-collapsed');
                    if (icon) icon.className = 'fa-solid fa-folder folder-icon';
                } else {
                    f.classList.remove('is-collapsed');
                    if (icon) icon.className = 'fa-solid fa-folder-open folder-icon';
                }
            });
            btnToggleAll.innerHTML = shouldCollapse
                ? '<i class="fa-solid fa-layer-group"></i> Mở Rộng Tất Cả'
                : '<i class="fa-solid fa-layer-group"></i> Thu Gọn Tất Cả';
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
    const badge = document.getElementById('selected-count-badge');
    if (badge) badge.textContent = selectedVideos.size;
    const pill = document.getElementById('selected-summary-pill-container');
    if (pill) {
        if (selectedVideos.size > 0) {
            pill.classList.add('has-selection');
        } else {
            pill.classList.remove('has-selection');
        }
    }
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
    const folderGroups = document.querySelectorAll('.folder-group');
    folderGroups.forEach(folderEl => {
        const nameText = folderEl.dataset.folderName || folderEl.querySelector('.folder-name-text')?.textContent.trim();
        const icon = folderEl.querySelector('.folder-icon');
        if (nameText === folderName) {
            folderEl.classList.remove('is-collapsed');
            if (icon) icon.className = 'fa-solid fa-folder-open folder-icon';
            // Check all unedited checkboxes inside this folder
            const checkboxes = folderEl.querySelectorAll('.video-checkbox');
            checkboxes.forEach(cb => {
                const isEdited = cb.dataset.edited === 'true';
                if (!isEdited) {
                    cb.checked = true;
                    selectedVideos.add(cb.dataset.path);
                }
            });
        } else {
            folderEl.classList.add('is-collapsed');
            if (icon) icon.className = 'fa-solid fa-folder folder-icon';
            const checkboxes = folderEl.querySelectorAll('.video-checkbox');
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
        showToast("Vui lòng chọn ít nhất 1 video để biên tập!", "warning");
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
        export_full: document.getElementById('export-full-toggle').value === 'yes',
        localization_settings: {
            target_lang: document.getElementById('localization-target-lang')?.value || 'none',
            voice_gender: document.getElementById('localization-voice-gender')?.value || 'male',
            dubbing_mode: document.getElementById('localization-dubbing-mode')?.value || 'dub_and_sub',
            sub_style: document.getElementById('localization-sub-style')?.value || 'tiktok-yellow'
        }
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
            showToast(`🚀 Đã bắt đầu biên tập batch cho ${videoItems.length} video!`, "success");
        } else {
            showToast("Render launch error: " + (data.error || "Unknown reason"), "error");
        }
    } catch (err) {
        showToast("API connection error: " + err.message, "error");
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
    const statusDot = document.querySelector('#system-status .status-dot') || document.querySelector('.status-dot');
    const statusText = document.getElementById('status-text');

    if (running) {
        if (btnStart) btnStart.classList.add('hidden');
        if (btnStop) btnStop.classList.remove('hidden');
        if (statusDot) statusDot.className = 'status-dot busy';
        if (statusText) statusText.textContent = 'Rendering videos...';
    } else {
        if (btnStart) btnStart.classList.remove('hidden');
        if (btnStop) btnStop.classList.add('hidden');
        if (statusDot) statusDot.className = 'status-dot online';
        if (statusText) statusText.textContent = 'Ready';
    }
}

// --- Sound & Visual Notifications ---
function playNotificationSound() {
    try {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        if (!AudioCtx) return;
        const ctx = new AudioCtx();
        const now = ctx.currentTime;
        
        // Chime Note 1
        const osc1 = ctx.createOscillator();
        const gain1 = ctx.createGain();
        osc1.type = 'sine';
        osc1.frequency.setValueAtTime(587.33, now); // D5
        osc1.frequency.exponentialRampToValueAtTime(880, now + 0.12); // A5
        gain1.gain.setValueAtTime(0.3, now);
        gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.5);
        osc1.connect(gain1);
        gain1.connect(ctx.destination);
        osc1.start(now);
        osc1.stop(now + 0.5);

        // Chime Note 2 (Success tone)
        const osc2 = ctx.createOscillator();
        const gain2 = ctx.createGain();
        osc2.type = 'sine';
        osc2.frequency.setValueAtTime(880, now + 0.12); // A5
        osc2.frequency.exponentialRampToValueAtTime(1174.66, now + 0.3); // D6
        gain2.gain.setValueAtTime(0.35, now + 0.12);
        gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.8);
        osc2.connect(gain2);
        gain2.connect(ctx.destination);
        osc2.start(now + 0.12);
        osc2.stop(now + 0.8);
    } catch (e) {
        // AudioContext silent fallback
    }
}

function navigateToTab(targetTab) {
    const tabLinks = document.querySelectorAll('.tab-link');
    const tabContents = document.querySelectorAll('.tab-content');
    const titleEl = document.getElementById('current-tab-title');
    const subEl = document.getElementById('current-tab-subtitle');
    const mainContent = document.querySelector('.app-main-content');

    tabLinks.forEach(l => l.classList.toggle('active', l.dataset.tab === targetTab));
    tabContents.forEach(c => c.classList.toggle('active', c.id === targetTab));

    const meta = (typeof TAB_HEADER_METADATA !== 'undefined') ? TAB_HEADER_METADATA[targetTab] : null;
    if (meta) {
        if (titleEl) titleEl.textContent = meta.title;
        if (subEl) subEl.textContent = meta.subtitle;
    }

    if (mainContent) mainContent.scrollTo({ top: 0, behavior: 'smooth' });

    if (targetTab === 'tab-outputs') {
        fetchResults();
    } else if (targetTab === 'tab-publishing') {
        fetchPublishingMatrix();
    } else if (targetTab === 'tab-autopilot') {
        loadAutopilotQueue();
    } else if (targetTab === 'tab-download') {
        onDownloadTabActivated();
    }
}
window.navigateToTab = navigateToTab;

async function updateProgressUI(data) {
    const percEl = document.getElementById('progress-percentage');
    const fillEl = document.getElementById('progress-fill');
    const taskEl = document.getElementById('progress-current-task');
    const statusEl = document.getElementById('render-status-text');
    const statusIndicator = document.getElementById('render-status-indicator');
    const term = document.getElementById('terminal-logs-window');
    const studioViewLogsBtn = document.getElementById('btn-studio-view-logs');
    const studioMiniProgress = document.getElementById('studio-mini-progress');

    const perc = data.percentage || 0;
    if (percEl) percEl.textContent = `${perc}%`;
    if (fillEl) fillEl.style.width = `${perc}%`;

    if (studioMiniProgress) studioMiniProgress.textContent = `${perc}%`;
    if (studioViewLogsBtn) {
        if (data.is_running) {
            studioViewLogsBtn.style.display = 'inline-flex';
            studioViewLogsBtn.classList.remove('hidden');
        } else {
            studioViewLogsBtn.style.display = 'none';
            studioViewLogsBtn.classList.add('hidden');
        }
    }

    // Đồng bộ nút bấm & trạng thái với máy chủ trên từng nhịp
    setProcessState(Boolean(data.is_running));

    if (data.is_running) {
        document.title = `(${perc}%) 🎬 Đang Render... - cris. studio`;
        if (taskEl) taskEl.textContent = data.current_task || "Đang xử lý video...";
        if (statusEl) statusEl.textContent = "Processing...";
    } else {
        if (perc >= 100) {
            document.title = `✅ ĐÃ XONG! - cris. studio`;
            if (taskEl) {
                taskEl.innerHTML = `<span style="color: #2ed573; font-weight: 700;">🎉 Hoàn tất toàn bộ batch!</span> <a href="#tab-outputs" onclick="navigateToTab('tab-outputs'); return false;" style="color: #3b82f6; text-decoration: underline; margin-left: 8px; font-weight: 600;">Xem Thư Viện Thành Phẩm ➔</a>`;
            }
            if (statusEl) statusEl.innerHTML = `<span style="color: #2ed573; font-weight: 700;">Completed</span>`;
        } else {
            document.title = `cris. studio - Video Automation Platform`;
            if (taskEl) taskEl.textContent = data.current_task || "Idle (No active tasks)";
            if (statusEl) statusEl.textContent = "Waiting...";
        }
    }

    if (statusIndicator) {
        const dot = statusIndicator.querySelector('.dot');
        if (dot) {
            dot.className = `dot ${data.is_running ? 'running' : (perc >= 100 ? 'completed' : 'idle')}`;
        }
    }

    // Update Logs with rich colorful styling
    if (data.logs && data.logs.length > 0 && term) {
        term.innerHTML = data.logs.map(l => {
            let cls = 'log-line';
            if (l.includes('✅') || l.includes('🎉') || l.includes('🏁')) cls += ' log-success';
            else if (l.includes('❌') || l.includes('⚠️')) cls += ' log-error';
            else if (l.includes('🔥') || l.includes('⚡') || l.includes('🚀')) cls += ' log-highlight';
            else if (l.includes('⚙️') || l.includes('▶️') || l.includes('🔍')) cls += ' log-info';
            return `<div class="${cls}">${escapeHtml(l)}</div>`;
        }).join('');
        if (terminalAutoScroll) {
            term.scrollTop = term.scrollHeight;
        }
        const logsCountEl = document.getElementById('terminal-logs-count');
        if (logsCountEl) logsCountEl.textContent = `${data.logs.length} dòng`;
    }

    // Luôn luôn đồng bộ trạng thái Auto-Pilot Hub (Nút bấm, tiến độ, logs) trên từng nhịp polling
    if (typeof updateAutopilotProgressUI === 'function') {
        updateAutopilotProgressUI(data);
    }
}

async function checkAndPollProgress() {
    try {
        const res = await fetch('/api/progress');
        const data = await res.json();
        await updateProgressUI(data);
        startPollingProgress();
    } catch (err) {
        console.error("checkAndPollProgress error:", err);
    }
}

// Tự động kiểm tra ngay lập tức khi người dùng quay lại tab trình duyệt từ Telegram/ứng dụng khác
document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
        checkAndPollProgress();
    }
});
window.addEventListener('focus', () => {
    checkAndPollProgress();
});

let lastLoggedFinishedState = false;

function startPollingProgress() {
    if (progressInterval) clearInterval(progressInterval);
    progressInterval = setInterval(async () => {
        try {
            const res = await fetch('/api/progress');
            const data = await res.json();
            
            const prevRunning = isRunning;
            await updateProgressUI(data);

            // Trigger completion event when transitioning from running to not running
            if (!data.is_running && prevRunning) {
                playNotificationSound();
                showToast("🎉 HOÀN TẤT BIÊN TẬP TẤT CẢ VIDEO! Các clip đã sẵn sàng trong Finished Library.");
                
                // Tự động hủy chọn các video vừa render xong và cập nhật lại bộ đếm
                selectedVideos.clear();
                updateSelectedVideosSummary();
                document.querySelectorAll('.video-item-checkbox:checked').forEach(cb => { cb.checked = false; });
                document.querySelectorAll('.video-item-card.selected').forEach(card => { card.classList.remove('selected'); });

                // HTML5 Desktop Notification
                if ('Notification' in window) {
                    if (Notification.permission === 'granted') {
                        new Notification("TikTok Studio Pro", {
                            body: "🎉 Đã hoàn tất biên tập toàn bộ video thành công!",
                            icon: "/favicon.png"
                        });
                    } else if (Notification.permission !== 'denied') {
                        Notification.requestPermission();
                    }
                }

                // Tự động làm mới danh sách thành phẩm & quét lại nguồn
                fetchResults();
                const source = document.getElementById('source-drive-link')?.value?.trim();
                if (source) scanSourcePath(source);

                setTimeout(() => {
                    document.title = "cris. studio - Video Automation Platform";
                }, 8000);
            }
        } catch (err) {
            console.error("Progress fetch error:", err);
        }
    }, 1000);
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
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/"/g, '&quot;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

function escapeJs(str) {
    if (!str) return '';
    return String(str)
        .replace(/\\/g, '\\\\')
        .replace(/'/g, "\\'")
        .replace(/"/g, '\\"')
        .replace(/\n/g, '\\n')
        .replace(/\r/g, '\\r');
}

let allFinishedResults = [];
let currentFinishedFilter = 'all';
let currentFinishedSearch = '';

async function fetchResults() {
    try {
        const dest = document.getElementById('dest-drive-link').value.trim();
        const res = await fetch(`/api/results?dest=${encodeURIComponent(dest)}`);
        const data = await res.json();

        allFinishedResults = data.results || [];
        
        // Update header count badge and filter tab counts
        const badgeCount = document.getElementById('finished-total-badge');
        if (badgeCount) {
            badgeCount.textContent = `${allFinishedResults.length} video${allFinishedResults.length === 1 ? '' : 's'}`;
        }

        const countAll = document.getElementById('count-finished-all');
        const countUnup = document.getElementById('count-finished-unuploaded');
        const countUp = document.getElementById('count-finished-uploaded');

        const unupCount = data.unuploaded_count !== undefined ? data.unuploaded_count : allFinishedResults.filter(r => !r.is_uploaded).length;
        const upCount = data.uploaded_count !== undefined ? data.uploaded_count : allFinishedResults.filter(r => r.is_uploaded).length;

        if (countAll) countAll.textContent = allFinishedResults.length;
        if (countUnup) countUnup.textContent = unupCount;
        if (countUp) countUp.textContent = upCount;

        renderFinishedLibrary();
    } catch (err) {
        console.error("Fetch results error:", err);
    }
}

function renderFinishedLibrary() {
    const container = document.getElementById('finished-list-container');
    if (!container) return;

    if (allFinishedResults.length === 0) {
        container.innerHTML = `
            <div class="empty-finished-state">
                <i class="fa-solid fa-clapperboard"></i>
                <p>Chưa có video thành phẩm nào trong thư mục đích.</p>
            </div>
        `;
        return;
    }

    // Lọc theo trạng thái Upload TikTok (all / unuploaded / uploaded)
    let filtered = allFinishedResults.filter(item => {
        if (currentFinishedFilter === 'unuploaded') return !item.is_uploaded;
        if (currentFinishedFilter === 'uploaded') return item.is_uploaded;
        return true;
    });

    // Lọc theo từ khóa tìm kiếm
    if (currentFinishedSearch) {
        filtered = filtered.filter(item => {
            const t = (item.title || '').toLowerCase();
            const f = (item.folder_name || '').toLowerCase();
            const a = (item.posted_account || '').toLowerCase();
            return t.includes(currentFinishedSearch) || f.includes(currentFinishedSearch) || a.includes(currentFinishedSearch);
        });
    }

    if (filtered.length === 0) {
        container.innerHTML = `
            <div class="empty-finished-state">
                <i class="fa-solid fa-filter-circle-xmark"></i>
                <p>Không tìm thấy video thành phẩm nào khớp với bộ lọc hiện tại.</p>
            </div>
        `;
        return;
    }

    // 1. Phân nhóm video theo từng Kênh YouTube
    const channelMap = new Map();
    filtered.forEach(item => {
        const channelName = item.folder_name || 'Khác';
        if (!channelMap.has(channelName)) {
            let channelPath = '';
            if (item.path) {
                const norm = item.path.replace(/\\/g, '/');
                const lastSlash = norm.lastIndexOf('/');
                if (lastSlash > 0) {
                    channelPath = norm.substring(0, lastSlash);
                }
            }
            channelMap.set(channelName, {
                channel: channelName,
                channelPath: channelPath,
                videos: [],
                maxMtime: 0,
                latestCreatedAt: '',
                totalParts: 0
            });
        }

        const grp = channelMap.get(channelName);
        grp.videos.push(item);
        grp.totalParts += (item.parts ? item.parts.length : 0);
        const itemMtime = Number(item.mtime || 0);
        if (itemMtime > grp.maxMtime) {
            grp.maxMtime = itemMtime;
            grp.latestCreatedAt = item.created_at || '';
        }
    });

    // 2. Sắp xếp các kênh: Kênh có video edit gần đây nhất (mtime lớn nhất) xếp lên đầu
    const sortedGroups = Array.from(channelMap.values()).sort((a, b) => b.maxMtime - a.maxMtime);

    // 3. Bên trong mỗi kênh: Sắp xếp các video theo ngày edit gần nhất đứng trước
    sortedGroups.forEach(grp => {
        grp.videos.sort((a, b) => (Number(b.mtime || 0)) - (Number(a.mtime || 0)));
    });

    const groupsHtml = sortedGroups.map(grp => {
        const channelCardsHtml = grp.videos.map(item => {
            // Status Badge
            const totalParts = (item.parts || []).length;
            const postedParts = (item.parts || []).filter(p => p.posted).length;
            let statusBadgeHtml = '';
            if (item.is_uploaded) {
                const partInfo = totalParts > 0 ? `(${totalParts}/${totalParts} parts)` : '';
                statusBadgeHtml = `<span class="badge-uploaded"><i class="fa-solid fa-circle-check"></i> Đã đăng TikTok ${partInfo} ${item.posted_account ? '(@' + escapeHtml(item.posted_account) + ')' : ''}</span>`;
            } else if (postedParts > 0) {
                statusBadgeHtml = `<span class="badge-uploading" style="background: rgba(245, 158, 11, 0.15); color: #f59e0b; border: 1px solid rgba(245, 158, 11, 0.3); border-radius: 9999px; padding: 2px 8px; font-size: 11px; font-weight: 700;"><i class="fa-solid fa-spinner fa-spin-pulse"></i> Đang đăng (${postedParts}/${totalParts} parts) ${item.posted_account ? '(@' + escapeHtml(item.posted_account) + ')' : ''}</span>`;
            } else {
                statusBadgeHtml = `<span class="badge-unuploaded"><i class="fa-solid fa-cloud-arrow-up"></i> Chưa upload ${totalParts > 0 ? '(' + totalParts + ' parts)' : ''}</span>`;
            }

            // Time Badge
            const timeBadgeHtml = item.created_at
                ? `<span class="badge-time" title="Thời gian render / chỉnh sửa"><i class="fa-regular fa-clock"></i> ${escapeHtml(item.created_at)}</span>`
                : '';

            // Tạo các nút part nhỏ để xem nhanh
            let partsHtml = '';
            if (item.parts && item.parts.length > 0) {
                partsHtml = `
                    <div class="finished-parts-chips">
                        ${item.parts.map((p, idx) => {
                            const partIsPosted = p.posted || false;
                            const partChipClass = `finished-part-chip ${partIsPosted ? 'is-posted' : ''}`;
                            const partIcon = partIsPosted
                                ? `<i class="fa-solid fa-check" style="font-size: 9px; color: #34d399;"></i>`
                                : `<i class="fa-solid fa-play" style="font-size: 8px;"></i>`;
                            const partTitle = `${escapeAttr(item.title)} - Part ${idx + 1} (${partIsPosted ? 'Posted' : 'Pending'})`;
                            return `
                                <button type="button" class="${partChipClass}" onclick="playFinishedVideo('${encodeURIComponent(p.url)}', '${partTitle}')" title="Xem trước ${escapeAttr(p.name)}">
                                    ${partIcon} Part ${idx + 1}
                                </button>
                            `;
                        }).join('')}
                    </div>
                `;
            }

            return `
                <div class="finished-card ${item.is_uploaded ? 'is-uploaded' : 'is-unuploaded'}">
                    <div class="finished-info" style="flex: 1; min-width: 0;">
                        <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                            <span class="finished-title" style="font-size: 13.5px; font-weight: 700; color: var(--text-primary);" title="${escapeAttr(item.title)}">
                                ${escapeHtml(item.title)}
                            </span>
                            ${statusBadgeHtml}
                            ${timeBadgeHtml}
                        </div>
                        ${partsHtml}
                    </div>
                    <div class="finished-actions" style="display: flex; align-items: center; gap: 8px; flex-shrink: 0;">
                        <span style="font-size: 12px; color: var(--text-muted); font-weight: 700; margin-right: 4px;">
                            ${item.parts.length} parts
                        </span>
                        <button class="btn btn-sm btn-secondary" onclick="openFinishedVideoFolder('${escapeJs(grp.channel)}', '${escapeJs(item.title)}')" title="Mở thư mục video trong File Explorer">
                            <i class="fa-solid fa-folder-open"></i> Thư mục
                        </button>
                        <button class="btn btn-sm btn-danger" onclick="deleteFinishedVideo('${escapeJs(item.path)}', '${escapeJs(item.title)}', '${escapeJs(item.folder_name)}')" title="Xóa video thành phẩm này">
                            <i class="fa-solid fa-trash-can"></i> Xóa
                        </button>
                    </div>
                </div>
            `;
        }).join('');

        return `
            <div class="finished-channel-group" data-channel="${escapeAttr(grp.channel)}">
                <div class="finished-channel-header" onclick="toggleFinishedChannelGroup(this)">
                    <div class="finished-channel-left">
                        <span class="finished-channel-icon"><i class="fa-brands fa-youtube"></i></span>
                        <div class="finished-channel-info">
                            <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                                <span class="finished-channel-name">${escapeHtml(grp.channel)}</span>
                                <span class="badge badge-primary" style="font-size: 11px; padding: 2px 8px;">${grp.videos.length} videos</span>
                                <span class="badge badge-neutral" style="font-size: 11px; padding: 2px 8px;">${grp.totalParts} parts</span>
                            </div>
                            <div class="finished-channel-meta">
                                ${grp.latestCreatedAt ? `<span><i class="fa-regular fa-clock"></i> Mới edit: <strong>${escapeHtml(grp.latestCreatedAt)}</strong></span>` : ''}
                            </div>
                        </div>
                    </div>
                    <div class="finished-channel-right" onclick="event.stopPropagation()">
                        <button type="button" class="btn btn-xs btn-outline" onclick="openFinishedChannelFolder('${escapeJs(grp.channel)}')" title="Mở thư mục kênh ${escapeAttr(grp.channel)} trong Explorer">
                            <i class="fa-solid fa-folder-open"></i> Thư mục kênh
                        </button>
                        <button type="button" class="btn btn-xs btn-ghost channel-collapse-btn" onclick="toggleFinishedChannelGroup(this.closest('.finished-channel-header'))" title="Thu gọn / Mở rộng kênh">
                            <i class="fa-solid fa-chevron-down channel-chevron"></i>
                        </button>
                    </div>
                </div>
                <div class="finished-channel-items">
                    ${channelCardsHtml}
                </div>
            </div>
        `;
    }).join('');

    container.innerHTML = groupsHtml;
}

function toggleFinishedChannelGroup(headerEl) {
    if (!headerEl) return;
    const group = headerEl.closest('.finished-channel-group');
    if (group) {
        group.classList.toggle('is-collapsed');
    }
}

let allFinishedChannelsCollapsed = false;
function toggleAllFinishedChannels() {
    const groups = document.querySelectorAll('.finished-channel-group');
    allFinishedChannelsCollapsed = !allFinishedChannelsCollapsed;
    groups.forEach(g => {
        if (allFinishedChannelsCollapsed) {
            g.classList.add('is-collapsed');
        } else {
            g.classList.remove('is-collapsed');
        }
    });
    const txt = document.getElementById('text-toggle-all-finished-channels');
    if (txt) {
        txt.textContent = allFinishedChannelsCollapsed ? 'Mở Rộng Tất Cả' : 'Thu Gọn Tất Cả';
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

function getCurrentDestinationDirectory() {
    const inputVal = document.getElementById('dest-drive-link')?.value?.trim();
    if (inputVal) return inputVal;
    if (typeof accountsData !== 'undefined' && accountsData?.dest_path) {
        return accountsData.dest_path.trim();
    }
    return 'D:/Antigravity/tiktok_running/output_product';
}

function openFinishedChannelFolder(channelName) {
    const dest = getCurrentDestinationDirectory();
    if (dest.startsWith('http://') || dest.startsWith('https://')) {
        window.open(dest, '_blank');
        return;
    }
    fetch('/api/open_folder', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            base_dest: dest,
            channel: channelName
        })
    });
}

function openFinishedVideoFolder(channelName, videoTitle) {
    const dest = getCurrentDestinationDirectory();
    if (dest.startsWith('http://') || dest.startsWith('https://')) {
        window.open(dest, '_blank');
        return;
    }
    fetch('/api/open_folder', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            base_dest: dest,
            channel: channelName,
            title: videoTitle
        })
    });
}

function openOutputDirectory(folderPath) {
    let target = folderPath;
    const dest = getCurrentDestinationDirectory();
    if (!target) {
        target = dest;
    }
    if (target.startsWith('http://') || target.startsWith('https://')) {
        window.open(target, '_blank');
        return;
    }
    fetch('/api/open_folder', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: target, base_dest: dest })
    });
}

// Bind methods to window for inline onclick handlers
window.openLocalFile = openLocalFile;
window.openOutputDirectory = openOutputDirectory;
window.openFinishedChannelFolder = openFinishedChannelFolder;
window.openFinishedVideoFolder = openFinishedVideoFolder;
window.getCurrentDestinationDirectory = getCurrentDestinationDirectory;
window.deleteFinishedVideo = deleteFinishedVideo;
window.deleteAllFinishedVideos = deleteAllFinishedVideos;
window.playFinishedVideo = playFinishedVideo;
window.escapeHtml = escapeHtml;
window.escapeAttr = escapeAttr;
window.escapeJs = escapeJs;

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
    if (btnSavePaths) {
        btnSavePaths.addEventListener('click', async (e) => {
            e.preventDefault();
            const source = document.getElementById('source-drive-link')?.value?.trim() || '';
            const dest = document.getElementById('dest-drive-link')?.value?.trim() || '';
            if (!source || !dest) {
                alert('Vui lòng nhập cả đường dẫn thư mục Source và Destination!');
                return;
            }
            
            const isWebLink = (str) => str.startsWith('http://') || str.startsWith('https://') || str.includes('drive.google.com');
            if (isWebLink(source) || isWebLink(dest)) {
                alert('Hệ thống chỉ chấp nhận thư mục cục bộ trên ổ cứng (ví dụ C:\\... hoặc D:\\...). Không chấp nhận link web Google Drive!');
                return;
            }

            accountsData.source_path = source;
            accountsData.dest_path = dest;
            const success = await saveAccountsToBackend();
            if (success) {
                showToast('🎉 Đã lưu đường dẫn thư mục thành công!');
                scanSourcePath(source);
            }
        });
    }
    
    // Toggle Channel Form
    if (btnToggleChannel && channelFormArea) {
        btnToggleChannel.addEventListener('click', () => {
            editingChannelIdx = -1;
            clearChannelForm();
            channelFormArea.classList.toggle('hidden');
            btnToggleChannel.innerHTML = channelFormArea.classList.contains('hidden') 
                ? '<i class="fa-solid fa-plus"></i> Add New Channel'
                : '<i class="fa-solid fa-xmark"></i> Close Form';
        });
    }
    
    if (btnCancelChannel && channelFormArea) {
        btnCancelChannel.addEventListener('click', (e) => {
            e.preventDefault();
            channelFormArea.classList.add('hidden');
            if (btnToggleChannel) btnToggleChannel.innerHTML = '<i class="fa-solid fa-plus"></i> Add New Channel';
            clearChannelForm();
        });
    }
    
    // Toggle Account Form
    if (btnToggleAccount && accountFormArea) {
        btnToggleAccount.addEventListener('click', () => {
            editingAccountIdx = -1;
            clearAccountForm();
            accountFormArea.classList.toggle('hidden');
            btnToggleAccount.innerHTML = accountFormArea.classList.contains('hidden')
                ? '<i class="fa-solid fa-plus"></i> Add New Account'
                : '<i class="fa-solid fa-xmark"></i> Close Form';
        });
    }
    
    if (btnCancelAccount && accountFormArea) {
        btnCancelAccount.addEventListener('click', (e) => {
            e.preventDefault();
            accountFormArea.classList.add('hidden');
            if (btnToggleAccount) btnToggleAccount.innerHTML = '<i class="fa-solid fa-plus"></i> Add New Account';
            clearAccountForm();
        });
    }
    
    // Eye icon inside Add Account form
    if (btnToggleInputPw && inputAccPassword) {
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
    }
    
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
    if (btnSaveChannel) {
        btnSaveChannel.addEventListener('click', async (e) => {
            e.preventDefault();
            const name = document.getElementById('input-channel-name')?.value?.trim() || '';
            const url = document.getElementById('input-channel-url')?.value?.trim() || '';
            let folder = document.getElementById('input-channel-folder')?.value?.trim() || '';
            const content = document.getElementById('input-channel-content')?.value?.trim() || '';
            
            if (!folder && name) {
                folder = name;
            }
            
            if (!name || !folder) {
                alert('Vui lòng nhập Tên Kênh YouTube và Tên Thư Mục Nguồn!');
                return;
            }
            
            btnSaveChannel.disabled = true;
            btnSaveChannel.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving...';
            
            try {
                accountsData.youtube_channels = accountsData.youtube_channels || [];
                const newChan = { name, url, folder_name: folder, content, note: 'Custom configured' };
                
                if (editingChannelIdx > -1 && editingChannelIdx < accountsData.youtube_channels.length) {
                    const oldChan = accountsData.youtube_channels[editingChannelIdx];
                    newChan.total_downloaded = oldChan.total_downloaded || 0;
                    accountsData.youtube_channels[editingChannelIdx] = newChan;
                } else {
                    newChan.total_downloaded = 0;
                    accountsData.youtube_channels.push(newChan);
                }
                
                const success = await saveAccountsToBackend();
                if (success) {
                    if (channelFormArea) channelFormArea.classList.add('hidden');
                    if (btnToggleChannel) btnToggleChannel.innerHTML = '<i class="fa-solid fa-plus"></i> Add New Channel';
                    clearChannelForm();
                    await fetchAccountsData();
                    showToast(`🎉 Đã lưu kênh YouTube: "${name}" thành công!`);
                    
                    // Tự động quét lại Source & Output để hiển thị ngay folder mới
                    const src = document.getElementById('source-drive-link')?.value?.trim() || '';
                    if (src) scanSourcePath(src);
                    fetchResults();
                    fetchPublishingMatrix();
                } else {
                    alert('❌ Không thể lưu kênh YouTube. Vui lòng kiểm tra lại kết nối server!');
                }
            } catch (err) {
                alert('❌ Lỗi khi lưu kênh: ' + err.message);
            } finally {
                btnSaveChannel.disabled = false;
                btnSaveChannel.innerHTML = 'Save Channel';
            }
        });
    }

    // Sync Accounts from AdsPower
    const btnSyncAdsAccounts = document.getElementById('btn-sync-adspower-accounts');
    if (btnSyncAdsAccounts) {
        btnSyncAdsAccounts.addEventListener('click', async () => {
            btnSyncAdsAccounts.disabled = true;
            btnSyncAdsAccounts.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Syncing...';
            try {
                const res = await fetch('/api/accounts/sync_adspower', { method: 'POST' });
                const data = await res.json();
                if (data.success) {
                    showToast(`🎉 Đã đồng bộ thành công ${data.total_accounts} tài khoản từ AdsPower!`);
                    await fetchAccountsData();
                    if (typeof fetchPublishingMatrix === 'function') {
                        fetchPublishingMatrix();
                    }
                    if (typeof fetchAdsPowerProfiles === 'function') {
                        fetchAdsPowerProfiles(true);
                    }
                } else {
                    alert('Lỗi khi đồng bộ từ AdsPower: ' + (data.error || 'Vui lòng kiểm tra lại ứng dụng AdsPower đang mở!'));
                }
            } catch (err) {
                alert('Lỗi kết nối khi đồng bộ: ' + err.message);
            } finally {
                btnSyncAdsAccounts.disabled = false;
                btnSyncAdsAccounts.innerHTML = '<i class="fa-solid fa-arrows-rotate text-primary"></i> Sync from AdsPower';
            }
        });
    }

    // Save Account
    if (btnSaveAccount) {
        btnSaveAccount.addEventListener('click', async (e) => {
            e.preventDefault();
            const username = document.getElementById('input-acc-username')?.value?.trim() || '';
            const email = document.getElementById('input-acc-email')?.value?.trim() || '';
            const ip = document.getElementById('input-acc-ip')?.value?.trim() || '';
            const group = document.getElementById('input-acc-group')?.value?.trim() || 'Default';
            const adspowerId = document.getElementById('input-acc-adspower')?.value?.trim() || '';
            const date = document.getElementById('input-acc-date')?.value?.trim() || '';
            const target = document.getElementById('input-acc-target')?.value || '';
            const hashtags = document.getElementById('input-acc-hashtags')?.value?.trim() || '';
            const content = document.getElementById('input-acc-content')?.value?.trim() || '';
            const note = document.getElementById('input-acc-note')?.value?.trim() || '';
            
            if (!username) {
                alert('Vui lòng nhập Tên tài khoản TikTok (Username)!');
                return;
            }
            
            btnSaveAccount.disabled = true;
            btnSaveAccount.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving...';
            
            try {
                accountsData.tiktok_accounts = accountsData.tiktok_accounts || [];
                const newAcc = {
                    account_name: username,
                    adspower_id: adspowerId,
                    adspower_serial: '',
                    adspower_name: username,
                    group_name: group,
                    ip: ip,
                    mail: email,
                    created_date: date,
                    target_channel: target,
                    content: content,
                    hashtag: hashtags,
                    note: note
                };
                
                if (editingAccountIdx > -1 && editingAccountIdx < accountsData.tiktok_accounts.length) {
                    const oldAcc = accountsData.tiktok_accounts[editingAccountIdx];
                    newAcc.posted_clips = oldAcc.posted_clips || {};
                    newAcc.target_history = oldAcc.target_history || [];
                    newAcc.adspower_serial = oldAcc.adspower_serial || '';
                    newAcc.country = oldAcc.country || '';
                    accountsData.tiktok_accounts[editingAccountIdx] = newAcc;
                } else {
                    newAcc.posted_clips = {};
                    newAcc.target_history = target ? [target] : [];
                    accountsData.tiktok_accounts.push(newAcc);
                }
                
                const success = await saveAccountsToBackend();
                if (success) {
                    if (accountFormArea) accountFormArea.classList.add('hidden');
                    if (btnToggleAccount) btnToggleAccount.innerHTML = '<i class="fa-solid fa-plus"></i> Add New Account';
                    clearAccountForm();
                    await fetchAccountsData();
                    showToast(`🎉 Đã lưu tài khoản TikTok: @${username} thành công!`);
                } else {
                    alert('❌ Không thể lưu tài khoản TikTok. Vui lòng thử lại!');
                }
            } catch (err) {
                alert('❌ Lỗi khi lưu tài khoản: ' + err.message);
            } finally {
                btnSaveAccount.disabled = false;
                btnSaveAccount.innerHTML = 'Save Account';
            }
        });
    }

    // Quick select AdsPower profile
    const selectAdsQuick = document.getElementById('select-acc-adspower-quick');
    if (selectAdsQuick) {
        selectAdsQuick.addEventListener('change', () => {
            const selectedOpt = selectAdsQuick.selectedOptions[0];
            if (selectedOpt && selectedOpt.dataset.profile) {
                try {
                    const p = JSON.parse(selectedOpt.dataset.profile);
                    const inputAds = document.getElementById('input-acc-adspower');
                    const inputGroup = document.getElementById('input-acc-group');
                    const inputIp = document.getElementById('input-acc-ip');
                    const inputDate = document.getElementById('input-acc-date');
                    const inputUser = document.getElementById('input-acc-username');
                    
                    if (inputAds) inputAds.value = p.user_id || p.serial_number || '';
                    if (inputGroup) inputGroup.value = p.group_name || 'Default';
                    if (inputIp) inputIp.value = p.ip || '';
                    if (inputDate && p.created_date) {
                        inputDate.value = p.created_date;
                    }
                    if (inputUser && (!inputUser.value.trim() || editingAccountIdx === -1)) {
                        inputUser.value = p.name || '';
                    }
                } catch (e) {
                    console.error('Error parsing profile dataset:', e);
                }
            }
        });
    }
    
    const btnRefreshAdsProfiles = document.getElementById('btn-refresh-adspower-profiles');
    if (btnRefreshAdsProfiles) {
        btnRefreshAdsProfiles.addEventListener('click', (e) => {
            e.preventDefault();
            if (typeof fetchAdsPowerProfiles === 'function') {
                fetchAdsPowerProfiles(true);
            }
        });
    }
    
    fetchAccountsData();
}

function clearChannelForm() {
    const n = document.getElementById('input-channel-name');
    const u = document.getElementById('input-channel-url');
    const f = document.getElementById('input-channel-folder');
    const c = document.getElementById('input-channel-content');
    if (n) n.value = '';
    if (u) u.value = '';
    if (f) f.value = '';
    if (c) c.value = '';
}

function clearAccountForm() {
    const fields = [
        'input-acc-username', 'select-acc-adspower-quick', 'input-acc-adspower',
        'input-acc-group', 'input-acc-ip', 'input-acc-date', 'input-acc-email',
        'input-acc-target', 'input-acc-hashtags', 'input-acc-content', 'input-acc-note'
    ];
    fields.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = '';
    });
}

async function fetchAccountsData() {
    const sourcePathInput = document.getElementById('source-drive-link');
    const destPathInput = document.getElementById('dest-drive-link');
    const currentSource = sourcePathInput?.value?.trim() || '';
    
    try {
        const res = await fetch(`/api/accounts?source=${encodeURIComponent(currentSource)}`);
        const data = await res.json();
        accountsData = data || { youtube_channels: [], tiktok_accounts: [] };
        
        let shouldScan = false;
        if (data.source_path && sourcePathInput && !currentSource) {
            sourcePathInput.value = data.source_path;
            shouldScan = true;
        }
        if (data.dest_path && destPathInput && !destPathInput.value.trim()) {
            destPathInput.value = data.dest_path;
        }
        
        renderChannelsTable();
        renderAccountsTable();
        updateTargetChannelDropdown();
        if (typeof populateDownloadChannelSelect === 'function') {
            populateDownloadChannelSelect();
        }
        
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
                <td colspan="7" class="table-empty">No YouTube channels configured.</td>
            </tr>
        `;
        return;
    }
    
    channels.forEach((chan, idx) => {
        const tr = document.createElement('tr');
        const contentDisplay = chan.content 
            ? `<span class="badge badge-neutral"><i class="fa-solid fa-tags"></i> ${escapeHtml(chan.content)}</span>`
            : '<span class="text-muted" style="font-size: 11px; opacity: 0.6;">-</span>';

        tr.innerHTML = `
            <td>${idx + 1}</td>
            <td><strong>${escapeHtml(chan.name)}</strong></td>
            <td>
                ${chan.url ? `<a href="${chan.url}" target="_blank" class="text-primary" style="text-decoration: none;"><i class="fa-solid fa-arrow-up-right-from-square"></i> View Channel</a>` : '<span class="text-muted">No URL</span>'}
            </td>
            <td><code>${escapeHtml(chan.folder_name)}</code></td>
            <td>${contentDisplay}</td>
            <td style="text-align: center;">
                <span class="badge badge-neutral">${chan.total_downloaded || 0} clips</span>
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
    if (!tbody) return;
    tbody.innerHTML = '';
    
    const accounts = accountsData.tiktok_accounts || [];
    if (accounts.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="8" class="table-empty">No TikTok accounts configured. Click "Sync from AdsPower" or "Add New Account".</td>
            </tr>
        `;
        return;
    }
    
    accounts.forEach((acc, idx) => {
        const tr = document.createElement('tr');
        
        // 1. Group Badge
        const isShared = acc.is_shared || (acc.group_name && acc.group_name.toLowerCase().includes('share'));
        const groupDisplay = acc.group_name
            ? `<span class="badge ${isShared ? 'badge-primary' : 'badge-neutral'}" title="${isShared ? 'Shared Group: ' + escapeHtml(acc.group_name) : 'Local Group: ' + escapeHtml(acc.group_name)}" style="font-size: 11px; max-width: 140px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; display: inline-flex; align-items: center; gap: 5px;">
                <i class="fa-solid ${isShared ? 'fa-share-nodes' : 'fa-folder'}"></i> ${escapeHtml(acc.group_name)}
               </span>`
            : '<span class="text-muted" style="font-size: 11px;">-</span>';

        // 2. Profile & IP
        const serialText = acc.adspower_serial ? `#${acc.adspower_serial}` : '';
        const idText = acc.adspower_id || '';
        const profileTag = (serialText || idText)
            ? `<div style="margin-bottom: 3px;"><span class="badge-adspower" title="AdsPower Profile ID"><i class="fa-solid fa-bolt"></i> ${escapeHtml(serialText ? `${serialText} (${idText})` : idText)}</span></div>`
            : `<div style="margin-bottom: 3px;"><span style="font-size:10px; opacity:0.6;"><i class="fa-solid fa-bolt"></i> Auto</span></div>`;

        const ipVal = acc.ip || acc.build_up_ip || acc.original_ip;
        const countryVal = acc.country ? `[${acc.country.toUpperCase()}] ` : '';
        const ipTag = ipVal
            ? `<div><span class="badge-ip" title="IP Address / Proxy"><i class="fa-solid fa-network-wired"></i> ${escapeHtml(countryVal + ipVal)}</span></div>`
            : `<div><span class="badge-ip" style="opacity: 0.5;" title="No IP"><i class="fa-solid fa-network-wired"></i> No IP</span></div>`;

        const profileAndIpDisplay = `
            ${profileTag}
            ${ipTag}
        `;
        
        // 3. Target YouTube Channel
        const matchingChan = (accountsData.youtube_channels || []).find(c => c.name === acc.target_channel);
        const chanUrl = matchingChan ? matchingChan.url : '';
        const targetChannelDisplay = chanUrl
            ? `<a href="${chanUrl}" target="_blank" class="badge badge-neutral" style="text-decoration: none;" title="Open YouTube channel"><i class="fa-brands fa-youtube text-danger"></i> ${escapeHtml(acc.target_channel)}</a>`
            : `<span class="badge badge-neutral">${escapeHtml(acc.target_channel || '-')}</span>`;

        tr.innerHTML = `
            <td>${idx + 1}</td>
            <td>
                <div style="font-weight: 700;">@${escapeHtml(acc.account_name)}</div>
                ${acc.mail ? `<div style="font-size: 11px; opacity:0.7;"><i class="fa-regular fa-envelope"></i> ${escapeHtml(acc.mail)}</div>` : ''}
                ${acc.content ? `<div style="font-size:11px; color:var(--text-secondary);"><i class="fa-solid fa-tags"></i> ${escapeHtml(acc.content)}</div>` : ''}
            </td>
            <td>${groupDisplay}</td>
            <td>${profileAndIpDisplay}</td>
            <td>${targetChannelDisplay}</td>
            <td><span style="font-size: 11px; white-space:nowrap;"><i class="fa-regular fa-calendar-days text-muted" style="margin-right: 4px;"></i>${escapeHtml(acc.created_date || '-')}</span></td>
            <td>
                ${acc.hashtag ? `<div style="font-size:11px; color:var(--primary); font-family:monospace; max-width: 150px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${escapeHtml(acc.hashtag)}">${escapeHtml(acc.hashtag)}</div>` : ''}
                ${acc.note ? `<div style="font-size:11px; opacity:0.7; max-width: 150px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${escapeHtml(acc.note)}">${escapeHtml(acc.note)}</div>` : ''}
            </td>
            <td style="text-align: center; white-space: nowrap;">
                <button class="btn btn-outline btn-xs btn-edit-acc" data-index="${idx}" style="padding: 4px 8px; font-size: 11px; margin-right: 4px;" title="Edit Account"><i class="fa-solid fa-pen"></i></button>
                <button class="btn btn-danger btn-xs btn-delete-acc" data-index="${idx}" style="padding: 4px 8px; font-size: 11px; background: var(--danger);" title="Delete Account"><i class="fa-solid fa-trash"></i></button>
            </td>
        `;
        
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
    if (!select) return;
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
    
    const n = document.getElementById('input-channel-name');
    const u = document.getElementById('input-channel-url');
    const f = document.getElementById('input-channel-folder');
    const c = document.getElementById('input-channel-content');
    if (n) n.value = chan.name;
    if (u) u.value = chan.url || '';
    if (f) f.value = chan.folder_name;
    if (c) c.value = chan.content || '';
    
    const formArea = document.getElementById('channel-form-area');
    if (formArea) {
        formArea.classList.remove('hidden');
        const btnToggle = document.getElementById('btn-toggle-channel-form');
        if (btnToggle) btnToggle.innerHTML = '<i class="fa-solid fa-xmark"></i> Close Form';
        formArea.scrollIntoView({ behavior: 'smooth' });
    }
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
    
    const setVal = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.value = val || '';
    };

    setVal('input-acc-username', acc.account_name);
    setVal('input-acc-adspower', acc.adspower_id || acc.adspower_serial || '');
    setVal('input-acc-group', acc.group_name || '');
    setVal('input-acc-ip', acc.ip || acc.build_up_ip || acc.original_ip || '');
    setVal('input-acc-date', acc.created_date || '');
    setVal('input-acc-email', acc.mail || '');
    setVal('input-acc-target', acc.target_channel || '');
    setVal('input-acc-hashtags', acc.hashtag || '');
    setVal('input-acc-content', acc.content || '');
    setVal('input-acc-note', acc.note || '');

    // Select AdsPower dropdown if matching
    const selectAds = document.getElementById('select-acc-adspower-quick');
    if (selectAds) {
        let matched = false;
        for (let i = 0; i < selectAds.options.length; i++) {
            const opt = selectAds.options[i];
            if (opt.value && (opt.value === acc.adspower_id || opt.value === String(acc.adspower_serial))) {
                selectAds.selectedIndex = i;
                matched = true;
                break;
            }
        }
        if (!matched) selectAds.selectedIndex = 0;
    }
    
    const formArea = document.getElementById('account-form-area');
    if (formArea) {
        formArea.classList.remove('hidden');
        const btnToggle = document.getElementById('btn-toggle-account-form');
        if (btnToggle) btnToggle.innerHTML = '<i class="fa-solid fa-xmark"></i> Close Form';
        formArea.scrollIntoView({ behavior: 'smooth' });
    }
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
                showToast('Tất cả các part đã được đăng!', 'info');
            }
        });
    }

    const btnBatchPostSelected = document.getElementById('btn-pub-batch-post-selected');
    if (btnBatchPostSelected) {
        btnBatchPostSelected.addEventListener('click', () => {
            const checkedChks = Array.from(document.querySelectorAll('.part-pill-chk:checked'));
            if (checkedChks.length === 0) {
                showToast('Vui lòng tích chọn ít nhất 1 Part trên danh sách để đăng!', 'warning');
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
                <span class="badge badge-neutral" style="font-size: 10px;">
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
    
    // Reset channel filter to 'all' on account switch so clips are never hidden
    activePublishingChannelFilter = 'all';
    const channelFilterSelect = document.getElementById('pub-filter-channel');
    if (channelFilterSelect) {
        channelFilterSelect.value = 'all';
    }

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
    
    // Update Channel Filter Dropdown options & validate active filter
    const channelFilterSelect = document.getElementById('pub-filter-channel');
    if (channelFilterSelect) {
        const uniqueChannels = Array.from(new Set(clips.map(c => c.channel).filter(Boolean)));
        
        // If current filter is not present in available channels, reset safely to 'all'
        if (activePublishingChannelFilter !== 'all' && !uniqueChannels.includes(activePublishingChannelFilter)) {
            activePublishingChannelFilter = 'all';
        }

        channelFilterSelect.innerHTML = '<option value="all">Tất cả nguồn kênh</option>';
        uniqueChannels.forEach(ch => {
            const opt = document.createElement('option');
            opt.value = ch;
            opt.textContent = `Kênh: ${ch}`;
            if (ch === activePublishingChannelFilter) opt.selected = true;
            channelFilterSelect.appendChild(opt);
        });
        channelFilterSelect.value = activePublishingChannelFilter;
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
        const isNoClips = clips.length === 0;
        const targetChan = acc.target_channel || 'Chưa gán';
        container.innerHTML = `
            <div class="empty-state" style="padding: 40px 20px; text-align: center;">
                <i class="fa-solid fa-film" style="font-size: 38px; color: var(--text-muted); margin-bottom: 12px; opacity: 0.6;"></i>
                <h4 style="margin: 0 0 8px; font-size: 15px; font-weight: 700;">${isNoClips ? `Chưa có video thành phẩm cho kênh "${escapeHtml(targetChan)}"` : 'Không có clip nào phù hợp với bộ lọc'}</h4>
                <p style="font-size: 12px; color: var(--text-secondary); max-width: 440px; margin: 0 auto 16px; line-height: 1.5;">
                    ${isNoClips 
                        ? `Thư mục đích chưa có video đã render từ kênh <strong>${escapeHtml(targetChan)}</strong>. Bạn có thể tải video từ YouTube hoặc xuất video trong Editor Studio!` 
                        : 'Thử chuyển bộ lọc về "All Clips" hoặc "Tất cả nguồn kênh" để xem toàn bộ danh sách.'}
                </p>
                ${isNoClips ? `
                    <div style="display: flex; gap: 10px; justify-content: center; flex-wrap: wrap;">
                        <button type="button" class="btn btn-sm btn-outline" onclick="document.querySelector('[data-tab=\\'tab-download\\']')?.click()">
                            <i class="fa-solid fa-cloud-arrow-down"></i> Tải video YouTube
                        </button>
                        <button type="button" class="btn btn-sm btn-primary" onclick="document.querySelector('[data-tab=\\'tab-studio\\']')?.click()">
                            <i class="fa-solid fa-wand-magic-sparkles"></i> Mở Editor Studio
                        </button>
                    </div>
                ` : `
                    <button type="button" class="btn btn-sm btn-outline" onclick="activePublishingChannelFilter='all';activePublishingFilter='all';document.querySelectorAll('.pub-filter-btn').forEach(b=>b.dataset.filter==='all'?b.classList.add('active'):b.classList.remove('active'));renderPublishingClipsFeed();">
                        <i class="fa-solid fa-rotate-left"></i> Đặt lại bộ lọc
                    </button>
                `}
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

        const totalPartsCount = (clip.parts || []).length;
        const postedPartsCount = (clip.parts || []).filter(p => p.posted).length;
        let postedTagHtml = '';
        if (clip.posted) {
            postedTagHtml = `<span class="pub-posted-tag"><i class="fa-solid fa-circle-check"></i> Đã đăng đủ part ${totalPartsCount > 0 ? '(' + totalPartsCount + '/' + totalPartsCount + ')' : ''} ${clip.posted_at ? `(${clip.posted_at})` : ''}</span>`;
        } else if (postedPartsCount > 0) {
            postedTagHtml = `<span class="pub-partial-tag" style="background: rgba(245, 158, 11, 0.15); color: #f59e0b; border: 1px solid rgba(245, 158, 11, 0.3); border-radius: 9999px; padding: 2px 8px; font-size: 11px; font-weight: 700;"><i class="fa-solid fa-spinner fa-spin-pulse"></i> Đang đăng (${postedPartsCount}/${totalPartsCount} part)</span>`;
        }

        const dateBadgeHtml = clip.created_at 
            ? `<span class="badge" style="background: rgba(255,255,255,0.06); font-size: 11px; color: var(--text-secondary); border: 1px solid var(--border-color);"><i class="fa-regular fa-clock"></i> ${escapeHtml(clip.created_at)}</span>` 
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
                        ${dateBadgeHtml}
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
                <button class="btn btn-sm btn-outline" onclick="openFinishedVideoFolder('${escapeJs(clip.channel)}', '${escapeJs(clip.title)}')" title="Mở thư mục chứa file">
                    <i class="fa-solid fa-folder-open"></i>
                </button>
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

    metaClipTitle.textContent = title;
    modalTitle.textContent = `Đang Đăng đồng thời ${partsToPost.length} Tab: "${title}"`;

    setStepState(stepHma, 'Đang chuẩn bị...', 'active');
    setStepState(stepAds, 'Chờ...', '');
    setStepState(stepUpload, 'Chờ...', '');
    setStepState(stepDone, 'Chờ...', '');

    appendLog(`🚀 BẮT ĐẦU QUY TRÌNH ĐĂNG ĐỒNG THỜI ${partsToPost.length} TAB CHO CLIP: "${title}"`);
    appendLog(`📋 Danh sách part: ${partsToPost.map(p => p.label || p.name).join(', ')}`);
    appendLog(`✨ Tiêu đề video (Caption): "${title}" (Chỉ dùng title, không kèm part_label, nạp tức thì)`);

    try {
        setTimeout(() => {
            if (stepHma.classList.contains('active')) {
                setStepState(stepHma, 'Đã chuyển IP', 'done');
                setStepState(stepAds, 'Đang mở profile...', 'active');
                appendLog(`⚡ Đang kết nối AdsPower Profile và mở ${partsToPost.length} tab mới...`);
            }
        }, 1500);

        setTimeout(() => {
            if (stepAds.classList.contains('active')) {
                setStepState(stepAds, 'Đã mở Chrome', 'done');
                setStepState(stepUpload, 'Đang tải lên...', 'active');
                appendLog(`🌐 Đang nạp ${partsToPost.length} video vào ${partsToPost.length} tab và điền tiêu đề đồng thời...`);
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
                items: partsToPost.map(p => ({
                    clip_key: clipKey,
                    channel: channel,
                    title: title,
                    video_file: p.file_path || '',
                    part_label: p.label || p.name || ''
                }))
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
            setStepState(stepDone, 'Thành công', 'done');
            appendLog(`🎉 ĐÃ HOÀN TẤT ĐĂNG ĐỒNG THỜI ${partsToPost.length} TAB CHO CLIP "${title}" THÀNH CÔNG!`);

            modalTitle.textContent = `Hoàn tất đăng ${partsToPost.length} Tab thành công`;
            btnFinish.disabled = false;
            btnFinish.innerHTML = '<i class="fa-solid fa-check"></i> Đã hoàn tất - Đóng';
            fetchPublishingMatrix();
        } else {
            setStepState(stepDone, 'Lỗi', 'error');
            appendLog(`❌ Lỗi khi đăng đồng thời: ${data.error || 'Thất bại'}`, true);
            btnFinish.disabled = false;
            btnFinish.innerHTML = '<i class="fa-solid fa-xmark"></i> Đóng';
        }
    } catch (err) {
        setStepState(stepDone, 'Lỗi kết nối', 'error');
        appendLog(`❌ Lỗi ngoại lệ: ${err.message}`, true);
        btnFinish.disabled = false;
        btnFinish.innerHTML = '<i class="fa-solid fa-xmark"></i> Đóng';
    }
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

    metaClipTitle.textContent = `${partsList.length} Clip / Part đã chọn`;
    modalTitle.textContent = `Đang Đăng đồng thời ${partsList.length} Tab lên @${acc.account_name}`;

    setStepState(stepHma, 'Đang chuẩn bị...', 'active');
    setStepState(stepAds, 'Chờ...', '');
    setStepState(stepUpload, 'Chờ...', '');
    setStepState(stepDone, 'Chờ...', '');

    appendLog(`🚀 BẮT ĐẦU ĐĂNG ĐỒNG THỜI ${partsList.length} TAB LÊN @${acc.account_name}...`);
    appendLog(`✨ Tiêu đề video (Caption): Tự động nạp tiêu đề gốc tức thì (không kèm part_label)`);

    try {
        setTimeout(() => {
            if (stepHma.classList.contains('active')) {
                setStepState(stepHma, 'Đã chuyển IP', 'done');
                setStepState(stepAds, 'Đang mở profile...', 'active');
                appendLog(`⚡ Đang kết nối AdsPower Profile và mở ${partsList.length} tab mới...`);
            }
        }, 1500);

        setTimeout(() => {
            if (stepAds.classList.contains('active')) {
                setStepState(stepAds, 'Đã mở Chrome', 'done');
                setStepState(stepUpload, 'Đang tải lên...', 'active');
                appendLog(`🌐 Đang nạp ${partsList.length} video vào ${partsList.length} tab và điền tiêu đề đồng thời...`);
            }
        }, 3500);

        const res = await fetch('/api/publishing/post_to_tiktok', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                account_name: activePublishingAccountName,
                items: partsList.map(item => ({
                    clip_key: item.clip_key,
                    channel: item.channel,
                    title: item.title,
                    video_file: item.file_path || '',
                    part_label: item.label || ''
                }))
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
            setStepState(stepDone, 'Thành công', 'done');
            appendLog(`🎉 ĐÃ HOÀN TẤT ĐĂNG ĐỒNG THỜI ${partsList.length} TAB LÊN @${acc.account_name} THÀNH CÔNG!`);

            fetchPublishingMatrix();
            modalTitle.textContent = `Hoàn tất đăng ${partsList.length} Tab thành công`;
            btnFinish.disabled = false;
            btnFinish.innerHTML = '<i class="fa-solid fa-check"></i> Đã hoàn tất - Đóng';
        } else {
            setStepState(stepDone, 'Lỗi', 'error');
            appendLog(`❌ Lỗi khi đăng đồng thời: ${data.error || 'Thất bại'}`, true);
            btnFinish.disabled = false;
            btnFinish.innerHTML = '<i class="fa-solid fa-xmark"></i> Đóng';
        }
    } catch (err) {
        setStepState(stepDone, 'Lỗi kết nối', 'error');
        appendLog(`❌ Ngoại lệ: ${err.message}`, true);
        btnFinish.disabled = false;
        btnFinish.innerHTML = '<i class="fa-solid fa-xmark"></i> Đóng';
    }
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
    const btnTestGemini = document.getElementById('btn-test-gemini-key');
    const btnToggleGemini = document.getElementById('btn-toggle-gemini-key');
    const selectGeminiModel = document.getElementById('select-gemini-model');
    const colCustomModel = document.getElementById('col-custom-model');
    const btnTestTelegram = document.getElementById('btn-test-telegram');
    const btnToggleTelegramToken = document.getElementById('btn-toggle-telegram-token');

    if (btnSaveAll) btnSaveAll.addEventListener('click', saveAllSettings);
    if (btnSavePaths) btnSavePaths.addEventListener('click', saveAllSettings);
    if (btnTestAdsPower) btnTestAdsPower.addEventListener('click', () => testAdsPowerConnection(false));
    if (btnTestHmaIp) btnTestHmaIp.addEventListener('click', () => checkHmaIp(false));
    if (btnTestHmaChange) btnTestHmaChange.addEventListener('click', testHmaChangeIp);
    if (btnHmaDisconnect) btnHmaDisconnect.addEventListener('click', disconnectHma);
    if (btnAutoDetectHma) btnAutoDetectHma.addEventListener('click', autoDetectHma);
    if (btnTestGemini) btnTestGemini.addEventListener('click', testGeminiConnection);
    if (btnTestTelegram) btnTestTelegram.addEventListener('click', testTelegramConnection);
    if (btnToggleGemini) {
        btnToggleGemini.addEventListener('click', () => {
            const input = document.getElementById('input-gemini-key');
            if (input) {
                input.type = (input.type === 'password') ? 'text' : 'password';
                btnToggleGemini.innerHTML = (input.type === 'password') ? '<i class="fa-solid fa-eye"></i>' : '<i class="fa-solid fa-eye-slash"></i>';
            }
        });
    }
    if (btnToggleTelegramToken) {
        btnToggleTelegramToken.addEventListener('click', () => {
            const input = document.getElementById('input-telegram-token');
            if (input) {
                input.type = (input.type === 'password') ? 'text' : 'password';
                btnToggleTelegramToken.innerHTML = (input.type === 'password') ? '<i class="fa-solid fa-eye"></i>' : '<i class="fa-solid fa-eye-slash"></i>';
            }
        });
    }

    if (selectGeminiModel && colCustomModel) {
        selectGeminiModel.addEventListener('change', () => {
            colCustomModel.style.display = (selectGeminiModel.value === 'custom') ? 'block' : 'none';
        });
    }

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

        // Gemini AI fields
        const geminiKey = document.getElementById('input-gemini-key');
        const geminiModelSelect = document.getElementById('select-gemini-model');
        const customModelInput = document.getElementById('input-custom-gemini-model');
        const colCustomModel = document.getElementById('col-custom-model');
        const geminiStyle = document.getElementById('select-gemini-style');
        const geminiBadge = document.getElementById('gemini-status-badge');

        if (geminiKey) geminiKey.value = data.gemini?.api_key || '';
        
        const savedModel = data.gemini?.model || 'gemini-3.7-flash';
        if (geminiModelSelect) {
            const knownOptions = Array.from(geminiModelSelect.options).map(o => o.value);
            if (knownOptions.includes(savedModel)) {
                geminiModelSelect.value = savedModel;
                if (colCustomModel) colCustomModel.style.display = 'none';
            } else {
                geminiModelSelect.value = 'custom';
                if (customModelInput) customModelInput.value = savedModel;
                if (colCustomModel) colCustomModel.style.display = 'block';
            }
        }
        if (geminiStyle) geminiStyle.value = data.gemini?.style || 'viral';

        if (geminiBadge) {
            if (data.gemini?.api_key) {
                geminiBadge.className = 'badge badge-success';
                geminiBadge.innerHTML = `<span class="status-dot online" style="width: 6px; height: 6px;"></span> Sẵn sàng (${savedModel})`;
            } else {
                geminiBadge.className = 'badge badge-secondary';
                geminiBadge.innerHTML = '<span class="status-dot offline" style="width: 6px; height: 6px;"></span> Chưa có Key';
            }
        }

        // Telegram Notification fields
        const tgToken = document.getElementById('input-telegram-token');
        const tgChatId = document.getElementById('input-telegram-chat-id');
        const tgBadge = document.getElementById('telegram-status-badge');
        if (tgToken) tgToken.value = data.telegram?.bot_token || '';
        if (tgChatId) tgChatId.value = data.telegram?.chat_id || '';
        if (tgBadge) {
            if (data.telegram?.bot_token && data.telegram?.chat_id) {
                tgBadge.className = 'badge badge-success';
                tgBadge.innerHTML = '<span class="status-dot online" style="width: 6px; height: 6px;"></span> Đã kết nối Bot';
            } else {
                tgBadge.className = 'badge badge-secondary';
                tgBadge.innerHTML = '<span class="status-dot offline" style="width: 6px; height: 6px;"></span> Chưa cấu hình';
            }
        }

        // TikTok preferences
        const postMode = document.getElementById('select-tiktok-post-mode');
        const closeBrowser = document.getElementById('select-tiktok-close-browser');
        const timeout = document.getElementById('input-tiktok-timeout');
        const dailyLimit = document.getElementById('input-tiktok-daily-limit');
        const blockVnIp = document.getElementById('checkbox-block-vn-ip');
        const stripPart = document.getElementById('checkbox-strip-part');

        if (postMode) postMode.value = data.tiktok_upload?.auto_submit ? 'auto_post' : 'draft';
        if (closeBrowser) closeBrowser.value = data.tiktok_upload?.close_browser_after_finish ? 'yes' : 'no';
        if (timeout) timeout.value = data.tiktok_upload?.wait_timeout || 60;
        if (dailyLimit) dailyLimit.value = data.tiktok_upload?.max_daily_posts_per_account || 3;
        if (blockVnIp) blockVnIp.checked = data.hma?.block_vietnam_ip !== false;
        if (stripPart) stripPart.checked = data.tiktok_upload?.strip_part_from_caption !== false;

        // Tự động kiểm tra AdsPower và IP ngầm
        testAdsPowerConnection(true);
        checkHmaIp(true);
    } catch (err) {
        console.error('Error fetching settings:', err);
    }
}

async function saveAllSettings(silent = false) {
    const sourcePath = document.getElementById('source-drive-link')?.value.trim() || '';
    const destPath = document.getElementById('dest-drive-link')?.value.trim() || '';
    const adspowerUrl = document.getElementById('input-adspower-url')?.value.trim() || 'http://local.adspower.net:50325';
    const adspowerKey = document.getElementById('input-adspower-key')?.value.trim() || '';
    const hmaPath = document.getElementById('input-hma-path')?.value.trim() || '';
    const hmaMode = document.getElementById('select-hma-mode')?.value || 'country';
    const hmaWait = parseInt(document.getElementById('input-hma-wait')?.value || 5);
    const geminiKey = document.getElementById('input-gemini-key')?.value.trim() || '';
    
    let geminiModel = document.getElementById('select-gemini-model')?.value || 'gemini-3.7-flash';
    if (geminiModel === 'custom') {
        geminiModel = document.getElementById('input-custom-gemini-model')?.value.trim() || 'gemini-3.7-flash';
    }
    const geminiStyle = document.getElementById('select-gemini-style')?.value || 'viral';

    const tgToken = document.getElementById('input-telegram-token')?.value.trim() || '';
    const tgChatId = document.getElementById('input-telegram-chat-id')?.value.trim() || '';

    const postMode = document.getElementById('select-tiktok-post-mode')?.value || 'auto_post';
    const closeBrowser = document.getElementById('select-tiktok-close-browser')?.value === 'yes';
    const timeout = parseInt(document.getElementById('input-tiktok-timeout')?.value || 60);
    const dailyLimit = parseInt(document.getElementById('input-tiktok-daily-limit')?.value || 3);
    const blockVnIp = document.getElementById('checkbox-block-vn-ip')?.checked !== false;
    const stripPart = document.getElementById('checkbox-strip-part')?.checked !== false;

    const payload = {
        adspower: {
            api_url: adspowerUrl,
            api_key: adspowerKey
        },
        hma: {
            cli_path: hmaPath,
            enabled: true,
            switch_mode: hmaMode,
            wait_seconds_after_switch: hmaWait,
            block_vietnam_ip: blockVnIp,
            require_foreign_ip: true
        },
        gemini: {
            api_key: geminiKey,
            model: geminiModel,
            style: geminiStyle
        },
        telegram: {
            bot_token: tgToken,
            chat_id: tgChatId,
            enabled: true
        },
        tiktok_upload: {
            auto_submit: (postMode === 'auto_post'),
            close_browser_after_finish: closeBrowser,
            wait_timeout: timeout,
            max_daily_posts_per_account: dailyLimit,
            strip_part_from_caption: stripPart
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
            if (!silent) showToast('🎉 Đã lưu toàn bộ cấu hình Settings & Workspaces thành công!', 'success');
        } else {
            if (!silent) showToast('Lỗi khi lưu cài đặt!', 'error');
        }
    } catch (err) {
        if (!silent) showToast('Lỗi kết nối khi lưu cài đặt: ' + err.message, 'error');
    }
}

async function testTelegramConnection() {
    const token = document.getElementById('input-telegram-token')?.value.trim() || '';
    const chatId = document.getElementById('input-telegram-chat-id')?.value.trim() || '';
    const resultSpan = document.getElementById('telegram-test-result');
    const badge = document.getElementById('telegram-status-badge');

    if (!token || !chatId) {
        alert('Vui lòng nhập đầy đủ Telegram Bot Token và Chat ID trước khi test!');
        return;
    }

    if (resultSpan) {
        resultSpan.style.color = 'var(--text-secondary)';
        resultSpan.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Đang gửi tin nhắn test đến Telegram...';
    }

    try {
        const res = await fetch('/api/telegram/test', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ bot_token: token, chat_id: chatId })
        });
        const data = await res.json();
        if (data.success) {
            if (resultSpan) {
                resultSpan.style.color = '#22c55e';
                resultSpan.innerHTML = '<i class="fa-solid fa-circle-check"></i> ' + data.message;
            }
            if (badge) {
                badge.className = 'badge badge-success';
                badge.innerHTML = '<span class="status-dot online" style="width: 6px; height: 6px;"></span> Đã kết nối Bot';
            }
            saveAllSettings(true);
        } else {
            if (resultSpan) {
                resultSpan.style.color = '#ef4444';
                resultSpan.innerHTML = '<i class="fa-solid fa-circle-exclamation"></i> ' + data.message;
            }
            if (badge) {
                badge.className = 'badge badge-danger';
                badge.innerHTML = '<span class="status-dot offline" style="width: 6px; height: 6px;"></span> Lỗi kết nối';
            }
        }
    } catch (err) {
        if (resultSpan) {
            resultSpan.style.color = '#ef4444';
            resultSpan.innerHTML = '<i class="fa-solid fa-circle-exclamation"></i> Lỗi kết nối: ' + err.message;
        }
    }
}

async function testGeminiConnection() {
    const key = document.getElementById('input-gemini-key')?.value.trim() || '';
    let model = document.getElementById('select-gemini-model')?.value || 'gemini-3.7-flash';
    if (model === 'custom') {
        model = document.getElementById('input-custom-gemini-model')?.value.trim() || 'gemini-3.7-flash';
    }
    const resultSpan = document.getElementById('gemini-test-result');
    const badge = document.getElementById('gemini-status-badge');

    if (!key) {
        alert('Vui lòng dán Google Gemini API Key vào ô nhập trước khi test!');
        return;
    }

    if (resultSpan) {
        resultSpan.style.color = 'var(--text-secondary)';
        resultSpan.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Đang kiểm tra kết nối với gói [${model}]...`;
    }

    try {
        const res = await fetch('/api/ai/test_key', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ api_key: key, model: model })
        });
        const data = await res.json();
        if (data.success) {
            if (resultSpan) {
                resultSpan.style.color = '#22c55e';
                resultSpan.innerHTML = '<i class="fa-solid fa-circle-check"></i> ' + data.message;
            }
            if (badge) {
                badge.className = 'badge badge-success';
                badge.innerHTML = `<span class="status-dot online" style="width: 6px; height: 6px;"></span> Sẵn sàng (${model})`;
            }
            saveAllSettings(true);
        } else {
            if (resultSpan) {
                resultSpan.style.color = '#ef4444';
                resultSpan.innerHTML = '<i class="fa-solid fa-circle-exclamation"></i> ' + data.message;
            }
            if (badge) {
                badge.className = 'badge badge-danger';
                badge.innerHTML = '<span class="status-dot offline" style="width: 6px; height: 6px;"></span> Key không hợp lệ';
            }
        }
    } catch (err) {
        if (resultSpan) {
            resultSpan.style.color = '#ef4444';
            resultSpan.innerHTML = '<i class="fa-solid fa-circle-exclamation"></i> Lỗi kết nối: ' + err.message;
        }
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
    
    // Group profiles by group_name
    const groups = {};
    profiles.forEach(p => {
        const g = p.group_name || 'Default';
        if (!groups[g]) groups[g] = [];
        groups[g].push(p);
    });

    Object.keys(groups).sort().forEach(groupName => {
        const optgroup = document.createElement('optgroup');
        const isShared = groupName.toLowerCase().includes('share');
        optgroup.label = `${isShared ? '🤝 ' : '📁 '}Group: ${groupName} (${groups[groupName].length})`;
        
        groups[groupName].forEach(p => {
            const opt = document.createElement('option');
            opt.value = p.user_id || p.serial_number;
            const ipStr = p.ip ? ` - IP: ${p.ip}` : '';
            opt.textContent = `[#${p.serial_number}] ${p.name || 'Unnamed'}${ipStr}`;
            opt.dataset.profile = JSON.stringify(p);
            optgroup.appendChild(opt);
        });
        selectQuick.appendChild(optgroup);
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
            showToast('Lỗi cập nhật trạng thái: ' + (data.error || 'Unknown'), 'error');
        }
    } catch (err) {
        showToast('Lỗi kết nối: ' + err.message, 'error');
    }
}

async function handleSwitchTargetChannel() {
    if (!activePublishingAccountName) return;

    const selectTarget = document.getElementById('pub-select-target');
    const btnChangeTarget = document.getElementById('btn-pub-change-target');
    const newTarget = selectTarget ? selectTarget.value.trim() : '';
    if (!newTarget) {
        showToast('Vui lòng chọn một kênh YouTube mục tiêu!', 'warning');
        return;
    }

    const accounts = publishingMatrixData.accounts || [];
    const acc = accounts.find(a => a.account_name === activePublishingAccountName);
    const oldTarget = acc?.target_channel || '';

    if (newTarget === oldTarget) {
        showToast(`Tài khoản "${activePublishingAccountName}" đã sử dụng kênh mục tiêu "${newTarget}" rồi!`, 'info');
        return;
    }

    if (btnChangeTarget) {
        btnChangeTarget.disabled = true;
        btnChangeTarget.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Switching...`;
    }

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
            if (acc) {
                acc.target_channel = newTarget;
            }

            // Reset active filters to 'all' so clips from the new channel are immediately displayed
            activePublishingChannelFilter = 'all';
            activePublishingFilter = 'all';

            // Reset UI filter button states
            document.querySelectorAll('.pub-filter-btn').forEach(btn => {
                if (btn.dataset.filter === 'all') btn.classList.add('active');
                else btn.classList.remove('active');
            });

            const channelFilterSelect = document.getElementById('pub-filter-channel');
            if (channelFilterSelect) {
                channelFilterSelect.value = 'all';
            }

            // Reload publishing matrix
            await fetchPublishingMatrix();

            // Also reload accounts data in Accounts Manager tab if function exists
            if (typeof fetchAccountsData === 'function') {
                try { fetchAccountsData(); } catch(e) {}
            }

            showToast(`🎯 Đã chuyển kênh mục tiêu sang "${newTarget}" thành công!`, 'success');
        } else {
            showToast('Lỗi chuyển đổi kênh: ' + (data.error || 'Unknown'), 'error');
        }
    } catch (err) {
        showToast('Lỗi kết nối: ' + err.message, 'error');
    } finally {
        if (btnChangeTarget) {
            btnChangeTarget.disabled = false;
            btnChangeTarget.innerHTML = `<i class="fa-solid fa-arrow-right-arrow-left"></i> Switch Target`;
        }
    }
}

function handleCopyAccountHashtags() {
    if (!activePublishingAccountName) return;
    const accounts = publishingMatrixData.accounts || [];
    const acc = accounts.find(a => a.account_name === activePublishingAccountName);
    if (!acc || !acc.hashtag) {
        showToast('Tài khoản này chưa có cấu hình Hashtag!', 'warning');
        return;
    }

    navigator.clipboard.writeText(acc.hashtag).then(() => {
        showToast(`📋 Đã sao chép Hashtag của tài khoản "${activePublishingAccountName}"!`, 'success');
    }).catch(() => {
        showToast('Không thể sao chép vào bộ nhớ tạm!', 'error');
    });
}

function handleCopyCaptionForClip(clipTitle) {
    if (!activePublishingAccountName) return;
    const accounts = publishingMatrixData.accounts || [];
    const acc = accounts.find(a => a.account_name === activePublishingAccountName);
    const hashtag = acc?.hashtag || '';
    const fullCaption = `${clipTitle}\n\n${hashtag}`.trim();

    navigator.clipboard.writeText(fullCaption).then(() => {
        showToast(`📋 Đã sao chép Caption + Hashtag của clip:\n"${clipTitle}"!`, 'success');
    }).catch(() => {
        showToast('Không thể sao chép vào bộ nhớ tạm!', 'error');
    });
}

async function handleBatchMarkAllPosted() {
    if (!activePublishingAccountName) return;
    const accounts = publishingMatrixData.accounts || [];
    const acc = accounts.find(a => a.account_name === activePublishingAccountName);
    if (!acc) return;

    const pendingClips = acc.clips?.filter(c => !c.posted) || [];
    if (pendingClips.length === 0) {
        showToast('Tất cả clip hiện tại đã được đánh dấu Đã Đăng rồi!', 'info');
        return;
    }

    if (!confirm(`Bạn có chắc chắn muốn đánh dấu ĐÃ ĐĂNG cho tất cả ${pendingClips.length} clips chưa đăng của tài khoản "${activePublishingAccountName}" không?`)) {
        return;
    }

    try {
        const res = await fetch('/api/publishing/batch_toggle_post', {
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
            showToast(`✅ Đã đánh dấu Đã Đăng cho ${pendingClips.length} clips thành công!`, 'success');
        } else {
            showToast('Lỗi cập nhật: ' + (data.error || 'Unknown'), 'error');
        }
    } catch (err) {
        showToast('Lỗi kết nối: ' + err.message, 'error');
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
   Utility Helpers
   ========================================================================== */
function copyTextToClipboard(text, successMsg = 'Đã copy vào bộ nhớ tạm!') {
    if (!text) return;
    if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(() => {
            showToast(successMsg);
        }).catch(() => {
            fallbackCopyText(text, successMsg);
        });
    } else {
        fallbackCopyText(text, successMsg);
    }
}

function fallbackCopyText(text, successMsg) {
    const textArea = document.createElement("textarea");
    textArea.value = text;
    textArea.style.position = "fixed";
    textArea.style.left = "-999999px";
    textArea.style.top = "-999999px";
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    try {
        document.execCommand('copy');
        showToast(successMsg);
    } catch (err) {
        prompt("Copy thủ công bên dưới:", text);
    }
    document.body.removeChild(textArea);
}

function showToast(message) {
    let toast = document.getElementById('studio-global-toast');
    if (!toast) {
        toast = document.createElement('div');
        toast.id = 'studio-global-toast';
        toast.style.position = 'fixed';
        toast.style.bottom = '24px';
        toast.style.right = '24px';
        toast.style.background = '#2ed573';
        toast.style.color = '#ffffff';
        toast.style.padding = '10px 18px';
        toast.style.borderRadius = '8px';
        toast.style.fontSize = '13px';
        toast.style.fontWeight = '700';
        toast.style.boxShadow = '0 6px 18px rgba(0,0,0,0.18)';
        toast.style.zIndex = '99999';
        toast.style.transition = 'all 0.3s ease';
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(10px)';
        document.body.appendChild(toast);
    }
    toast.innerText = message;
    toast.style.opacity = '1';
    toast.style.transform = 'translateY(0)';
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(10px)';
    }, 2400);
}

window.copyTextToClipboard = copyTextToClipboard;

/* ==========================================================================
   Auto-Pilot Pipeline Hub (All-in-One Automation & Accounts Queue Table)
   ========================================================================== */
let isAutopilotRunning = false;
let autopilotCancelRequested = false;
let pendingQueueRawCache = [];
let pendingQueueFilteredCache = [];
let selectedAutopilotAccounts = null; // null: auto-select accounts with clips, or Set<string>
let autopilotFilterGroup = 'all';
let autopilotFilterStatus = 'all'; // 'all', 'has_clips', 'completed'
let autopilotSearchQuery = '';
let expandedAutopilotAccounts = new Set(); // Set of account_name strings whose accordion is expanded

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

    // Toolbar Controls
    const groupSelect = document.getElementById('autopilot-filter-group');
    const statusSelect = document.getElementById('autopilot-filter-status');
    const searchInput = document.getElementById('autopilot-search-account');
    const btnClearSearch = document.getElementById('btn-clear-autopilot-search');

    if (groupSelect) {
        groupSelect.addEventListener('change', (e) => {
            autopilotFilterGroup = e.target.value;
            renderAutopilotUI();
        });
    }

    if (statusSelect) {
        statusSelect.addEventListener('change', (e) => {
            autopilotFilterStatus = e.target.value;
            renderAutopilotUI();
        });
    }

    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            autopilotSearchQuery = e.target.value.trim().toLowerCase();
            if (btnClearSearch) {
                btnClearSearch.classList.toggle('hidden', !autopilotSearchQuery);
            }
            renderAutopilotUI();
        });
    }

    if (btnClearSearch) {
        btnClearSearch.addEventListener('click', () => {
            if (searchInput) searchInput.value = '';
            autopilotSearchQuery = '';
            btnClearSearch.classList.add('hidden');
            renderAutopilotUI();
        });
    }

    // Master Checkbox
    const chkMaster = document.getElementById('chk-autopilot-master');
    if (chkMaster) {
        chkMaster.addEventListener('change', (e) => {
            const isChecked = e.target.checked;
            const visible = getVisibleAutopilotAccounts();
            if (!selectedAutopilotAccounts) selectedAutopilotAccounts = new Set();
            visible.forEach(acc => {
                if (isChecked) {
                    selectedAutopilotAccounts.add(acc.name);
                } else {
                    selectedAutopilotAccounts.delete(acc.name);
                }
            });
            renderAutopilotUI();
        });
    }

    // Batch Action Buttons
    const btnPageAccSelectAll = document.getElementById('btn-page-acc-select-all');
    const btnPageAccSelectHasClips = document.getElementById('btn-page-acc-select-has-clips');
    const btnPageAccSelectNone = document.getElementById('btn-page-acc-select-none');
    const btnToggleExpandAll = document.getElementById('btn-toggle-expand-all-accs');

    // Modal buttons (for backwards compatibility if modal opened)
    const btnModalAccSelectAll = document.getElementById('btn-modal-acc-select-all');
    const btnModalAccDeselectAll = document.getElementById('btn-modal-acc-deselect-all');

    if (btnPageAccSelectAll) {
        btnPageAccSelectAll.addEventListener('click', () => {
            const visible = getVisibleAutopilotAccounts();
            if (!selectedAutopilotAccounts) selectedAutopilotAccounts = new Set();
            visible.forEach(acc => selectedAutopilotAccounts.add(acc.name));
            renderAutopilotUI();
        });
    }

    if (btnPageAccSelectHasClips) {
        btnPageAccSelectHasClips.addEventListener('click', () => {
            const visible = getVisibleAutopilotAccounts();
            if (!selectedAutopilotAccounts) selectedAutopilotAccounts = new Set();
            visible.forEach(acc => {
                if (acc.clips.length > 0) {
                    selectedAutopilotAccounts.add(acc.name);
                } else {
                    selectedAutopilotAccounts.delete(acc.name);
                }
            });
            renderAutopilotUI();
        });
    }

    if (btnPageAccSelectNone) {
        btnPageAccSelectNone.addEventListener('click', () => {
            selectedAutopilotAccounts = new Set();
            renderAutopilotUI();
        });
    }

    if (btnToggleExpandAll) {
        btnToggleExpandAll.addEventListener('click', () => {
            const visibleWithClips = getVisibleAutopilotAccounts().filter(a => a.clips.length > 0);
            if (visibleWithClips.length === 0) return;
            const allExpanded = visibleWithClips.every(a => expandedAutopilotAccounts.has(a.name));
            if (allExpanded) {
                visibleWithClips.forEach(a => expandedAutopilotAccounts.delete(a.name));
            } else {
                visibleWithClips.forEach(a => expandedAutopilotAccounts.add(a.name));
            }
            renderAutopilotUI();
        });
    }

    if (btnModalAccSelectAll) {
        btnModalAccSelectAll.addEventListener('click', () => {
            const allAccs = Array.from(new Set(pendingQueueRawCache.map(i => i.account_name)));
            selectedAutopilotAccounts = new Set(allAccs);
            renderAutopilotUI();
        });
    }

    if (btnModalAccDeselectAll) {
        btnModalAccDeselectAll.addEventListener('click', () => {
            selectedAutopilotAccounts = new Set();
            renderAutopilotUI();
        });
    }

    // Modal Opening & Closing
    if (btnOpenModal && modal) {
        btnOpenModal.addEventListener('click', () => {
            modal.classList.remove('hidden');
            loadAutopilotQueue();
        });
    }

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

    // Sync History with Queue
    const btnSyncHistoryPage = document.getElementById('btn-page-sync-history');
    if (btnSyncHistoryPage) {
        btnSyncHistoryPage.addEventListener('click', async () => {
            const oldHtml = btnSyncHistoryPage.innerHTML;
            btnSyncHistoryPage.disabled = true;
            btnSyncHistoryPage.innerHTML = '<i class="fa-solid fa-spinner fa-spin text-primary"></i> Đang đồng bộ...';
            try {
                const res = await fetch('/api/publishing/sync_history', { method: 'POST' });
                const data = await res.json();
                if (data.success) {
                    showToast(`🎉 ${data.message || 'Đã đồng bộ lịch sử đăng thành công!'}`);
                    await loadAutopilotQueue();
                } else {
                    showToast(`❌ Không thể đồng bộ: ${data.error || 'Lỗi không xác định'}`);
                }
            } catch (err) {
                showToast(`❌ Lỗi kết nối: ${err.message}`);
            } finally {
                btnSyncHistoryPage.disabled = false;
                btnSyncHistoryPage.innerHTML = oldHtml;
            }
        });
    }

    // Open n8n Dashboard
    const openN8nHandler = () => window.open('http://localhost:5678', '_blank');
    if (btnOpenN8nModal) btnOpenN8nModal.addEventListener('click', openN8nHandler);
    if (btnOpenN8nPage) btnOpenN8nPage.addEventListener('click', openN8nHandler);

    // Start / Stop Pipeline
    if (btnStartModal) btnStartModal.addEventListener('click', startAutopilotPipeline);
    if (btnStartPage) btnStartPage.addEventListener('click', startAutopilotPipeline);
    if (btnStopModal) btnStopModal.addEventListener('click', stopAutopilotPipeline);
    if (btnStopPage) btnStopPage.addEventListener('click', stopAutopilotPipeline);

    syncAutopilotButtonState();
    loadAutopilotQueue();
}

async function syncAutopilotButtonState() {
    try {
        const res = await fetch('/api/autopilot/status');
        const data = await res.json();
        const isRunning = (data && data.is_running) || false;
        isAutopilotRunning = isRunning;

        const btnStartModal = document.getElementById('btn-start-autopilot');
        const btnStopModal = document.getElementById('btn-stop-autopilot');
        const btnStartPage = document.getElementById('btn-page-start-autopilot');
        const btnStopPage = document.getElementById('btn-page-stop-autopilot');
        const statusBadgePage = document.getElementById('tab-autopilot-status-badge');
        const miniBtn = document.getElementById('btn-autopilot-view-logs');

        if (isRunning) {
            if (btnStartModal) btnStartModal.classList.add('hidden');
            if (btnStopModal) btnStopModal.classList.remove('hidden');
            if (btnStartPage) btnStartPage.classList.add('hidden');
            if (btnStopPage) btnStopPage.classList.remove('hidden');
            if (statusBadgePage) {
                statusBadgePage.textContent = 'Đang chạy...';
                statusBadgePage.className = 'badge badge-primary';
            }
            if (miniBtn) {
                miniBtn.style.display = 'inline-flex';
                miniBtn.classList.remove('hidden');
            }
        } else {
            if (btnStartModal) btnStartModal.classList.remove('hidden');
            if (btnStopModal) btnStopModal.classList.add('hidden');
            if (btnStartPage) btnStartPage.classList.remove('hidden');
            if (btnStopPage) btnStopPage.classList.add('hidden');
            if (miniBtn) {
                miniBtn.style.display = 'none';
                miniBtn.classList.add('hidden');
            }
            if (statusBadgePage) {
                if (data.state && (data.state.success_count > 0 || data.state.fail_count > 0)) {
                    statusBadgePage.textContent = 'Đã hoàn thành';
                    statusBadgePage.className = 'badge badge-success';
                } else if (statusBadgePage.textContent === 'Đang chạy...') {
                    statusBadgePage.textContent = 'Sẵn sàng';
                    statusBadgePage.className = 'badge badge-secondary';
                }
            }
        }
    } catch (e) {}
}

function buildAutopilotAccountsModel() {
    const accClipsMap = {};
    for (const item of pendingQueueRawCache) {
        const acc = item.account_name;
        if (!acc) continue;
        if (!accClipsMap[acc]) accClipsMap[acc] = [];
        accClipsMap[acc].push(item);
    }

    const map = new Map();
    const registeredAccs = (typeof accountsData !== 'undefined' && accountsData.tiktok_accounts) || [];

    registeredAccs.forEach(a => {
        if (!a || !a.account_name) return;
        const name = a.account_name;
        map.set(name, {
            name: name,
            group_name: a.group_name || 'Default',
            target_channel: a.target_channel || '',
            target_ip: a.build_up_ip || a.country || a.ip || a.original_ip || 'US',
            ads_id: a.adspower_id || a.serial_number || '',
            clips: accClipsMap[name] || []
        });
    });

    Object.keys(accClipsMap).forEach(name => {
        if (!map.has(name)) {
            const firstClip = accClipsMap[name][0] || {};
            map.set(name, {
                name: name,
                group_name: 'Default',
                target_channel: firstClip.channel || '',
                target_ip: firstClip.target_ip || firstClip.country || 'US',
                ads_id: '',
                clips: accClipsMap[name]
            });
        }
    });

    return Array.from(map.values());
}

function getVisibleAutopilotAccounts() {
    const allAccounts = buildAutopilotAccountsModel();
    let list = allAccounts;

    // 1. Group filter
    if (autopilotFilterGroup && autopilotFilterGroup !== 'all') {
        list = list.filter(a => a.group_name === autopilotFilterGroup);
    }

    // 2. Status filter
    if (autopilotFilterStatus === 'has_clips') {
        list = list.filter(a => a.clips.length > 0);
    } else if (autopilotFilterStatus === 'completed') {
        list = list.filter(a => a.clips.length === 0);
    }

    // 3. Search query
    if (autopilotSearchQuery) {
        list = list.filter(a =>
            a.name.toLowerCase().includes(autopilotSearchQuery) ||
            a.target_channel.toLowerCase().includes(autopilotSearchQuery) ||
            (a.group_name && a.group_name.toLowerCase().includes(autopilotSearchQuery))
        );
    }

    return list;
}

async function loadAutopilotQueue() {
    syncAutopilotButtonState();
    const queueBadgeModal = document.getElementById('autopilot-queue-badge');
    const queuePreviewModal = document.getElementById('autopilot-queue-preview');
    const queueCountPage = document.getElementById('tab-autopilot-queue-count');
    const accountsCountPage = document.getElementById('tab-autopilot-accounts-count');
    const tableBodyPage = document.getElementById('tab-autopilot-accounts-table-body');

    if (queueBadgeModal) queueBadgeModal.textContent = 'Đang quét...';
    if (queuePreviewModal) queuePreviewModal.innerHTML = '<div style="color: var(--text-secondary); text-align: center; padding: 10px;">Đang tải danh sách clip chờ đăng...</div>';
    if (tableBodyPage) tableBodyPage.innerHTML = '<tr><td colspan="7" class="table-empty"><i class="fa-solid fa-circle-notch fa-spin"></i> Đang tải danh sách tài khoản và hàng đợi...</td></tr>';

    try {
        if (typeof fetchAccountsData === 'function' && (!accountsData || !accountsData.tiktok_accounts || accountsData.tiktok_accounts.length === 0)) {
            try { await fetchAccountsData(); } catch (e) {}
        }

        const res = await fetch('/api/n8n/pending_clips?only_current_target=true');
        const data = await res.json();
        if (data.success) {
            pendingQueueRawCache = data.items || [];
            
            const allModels = buildAutopilotAccountsModel();
            const accountsWithClips = allModels.filter(a => a.clips.length > 0).map(a => a.name);

            // Mặc định ban đầu chọn tất cả tài khoản CÓ clip
            if (selectedAutopilotAccounts === null) {
                selectedAutopilotAccounts = new Set(accountsWithClips.length > 0 ? accountsWithClips : allModels.map(a => a.name));
            }

            renderAutopilotUI();
        } else {
            if (tableBodyPage) tableBodyPage.innerHTML = `<tr><td colspan="7" style="color: #ef4444; text-align: center;">Lỗi tải hàng đợi: ${data.error || 'Lỗi không xác định'}</td></tr>`;
        }
    } catch (err) {
        if (queueBadgeModal) queueBadgeModal.textContent = 'Lỗi quét';
        if (queuePreviewModal) queuePreviewModal.innerHTML = `<div style="color: #ef4444; padding: 8px;">Lỗi kết nối: ${err.message}</div>`;
        if (tableBodyPage) tableBodyPage.innerHTML = `<tr><td colspan="7" style="color: #ef4444; text-align: center;">Lỗi kết nối: ${err.message}</td></tr>`;
    }
}

function renderAutopilotUI() {
    const allModels = buildAutopilotAccountsModel();
    if (!selectedAutopilotAccounts) selectedAutopilotAccounts = new Set();

    // 1. Populate Group Filter Dropdown
    const groupSelect = document.getElementById('autopilot-filter-group');
    if (groupSelect) {
        const groupsSet = new Set();
        const groupCountMap = {};
        allModels.forEach(a => {
            const g = a.group_name || 'Default';
            groupsSet.add(g);
            groupCountMap[g] = (groupCountMap[g] || 0) + 1;
        });

        const groupsArr = Array.from(groupsSet).sort();
        const currentVal = autopilotFilterGroup || 'all';

        let optionsHtml = `<option value="all" ${currentVal === 'all' ? 'selected' : ''}>Tất cả Groups (${allModels.length})</option>`;
        groupsArr.forEach(g => {
            optionsHtml += `<option value="${escapeHtml(g)}" ${currentVal === g ? 'selected' : ''}>${escapeHtml(g)} (${groupCountMap[g]})</option>`;
        });
        groupSelect.innerHTML = optionsHtml;
    }

    const visibleAccounts = getVisibleAutopilotAccounts();

    // 2. Master Checkbox State
    const chkMaster = document.getElementById('chk-autopilot-master');
    if (chkMaster) {
        if (visibleAccounts.length === 0) {
            chkMaster.checked = false;
            chkMaster.indeterminate = false;
        } else {
            const selectedVisibleCount = visibleAccounts.filter(a => selectedAutopilotAccounts.has(a.name)).length;
            if (selectedVisibleCount === visibleAccounts.length) {
                chkMaster.checked = true;
                chkMaster.indeterminate = false;
            } else if (selectedVisibleCount > 0) {
                chkMaster.checked = false;
                chkMaster.indeterminate = true;
            } else {
                chkMaster.checked = false;
                chkMaster.indeterminate = false;
            }
        }
    }

    // 3. Expand / Collapse All Button Label & Icon
    const btnToggleExpandAll = document.getElementById('btn-toggle-expand-all-accs');
    if (btnToggleExpandAll) {
        const visibleWithClips = visibleAccounts.filter(a => a.clips.length > 0);
        const isAllExpanded = visibleWithClips.length > 0 && visibleWithClips.every(a => expandedAutopilotAccounts.has(a.name));
        if (isAllExpanded) {
            btnToggleExpandAll.innerHTML = '<i class="fa-solid fa-chevron-up"></i> Thu gọn tất cả';
        } else {
            btnToggleExpandAll.innerHTML = '<i class="fa-solid fa-chevron-down"></i> Mở rộng tất cả';
        }
    }

    // 4. Update Summary Badges & Hero Counts
    let totalSelectedClips = 0;
    allModels.forEach(a => {
        if (selectedAutopilotAccounts.has(a.name)) {
            totalSelectedClips += a.clips.length;
        }
    });

    const pageAccBadge = document.getElementById('autopilot-selected-acc-badge');
    if (pageAccBadge) {
        pageAccBadge.textContent = `Đã chọn: ${selectedAutopilotAccounts.size}/${allModels.length} tài khoản (${totalSelectedClips} clip)`;
    }

    const queueCountPage = document.getElementById('tab-autopilot-queue-count');
    const accountsCountPage = document.getElementById('tab-autopilot-accounts-count');
    if (queueCountPage) queueCountPage.textContent = `${totalSelectedClips} Clip`;
    if (accountsCountPage) accountsCountPage.textContent = `${selectedAutopilotAccounts.size} Acc`;

    // 5. Update Modal UI (if present)
    const queueBadgeModal = document.getElementById('autopilot-queue-badge');
    const modalAccBadge = document.getElementById('autopilot-modal-selected-acc-badge');
    const modalAccList = document.getElementById('autopilot-modal-accounts-list');
    const queuePreviewModal = document.getElementById('autopilot-queue-preview');

    if (queueBadgeModal) {
        queueBadgeModal.textContent = `${totalSelectedClips} clip sẵn sàng`;
        queueBadgeModal.className = totalSelectedClips > 0 ? 'badge badge-primary' : 'badge badge-secondary';
    }
    if (modalAccBadge) {
        modalAccBadge.textContent = `${selectedAutopilotAccounts.size}/${allModels.length} tài khoản`;
    }

    if (modalAccList) {
        modalAccList.innerHTML = allModels.map(acc => {
            const isSel = selectedAutopilotAccounts.has(acc.name);
            return `
                <button type="button" class="btn btn-xs ${isSel ? 'btn-primary' : 'btn-outline'}"
                        data-autopilot-acc="${escapeHtml(acc.name)}"
                        style="display: inline-flex; align-items: center; gap: 5px; font-weight: 700; border-radius: 6px; padding: 4px 8px; cursor: pointer;">
                    <i class="fa-solid ${isSel ? 'fa-square-check text-success' : 'fa-square'}"></i>
                    <span>@${escapeHtml(acc.name)}</span>
                    <span class="badge ${isSel ? 'badge-info' : 'badge-secondary'}" style="font-size: 9.5px; padding: 1px 4px;">${acc.clips.length} clip</span>
                </button>
            `;
        }).join('');

        modalAccList.querySelectorAll('[data-autopilot-acc]').forEach(btn => {
            btn.addEventListener('click', () => {
                const acc = btn.getAttribute('data-autopilot-acc');
                if (selectedAutopilotAccounts.has(acc)) {
                    selectedAutopilotAccounts.delete(acc);
                } else {
                    selectedAutopilotAccounts.add(acc);
                }
                renderAutopilotUI();
            });
        });
    }

    if (queuePreviewModal) {
        const filteredClips = pendingQueueRawCache.filter(i => selectedAutopilotAccounts.has(i.account_name));
        if (filteredClips.length === 0) {
            queuePreviewModal.innerHTML = '<div style="color: var(--text-secondary); padding: 8px; text-align: center;"><i class="fa-solid fa-circle-check text-success"></i> Không có clip nào cho các tài khoản được chọn.</div>';
        } else {
            queuePreviewModal.innerHTML = filteredClips.map((item, idx) => `
                <div style="display: flex; justify-content: space-between; align-items: center; background: rgba(0,0,0,0.08); padding: 6px 10px; border-radius: 6px; border: 1px solid var(--border-color);">
                    <div style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 70%;">
                        <span style="font-weight: 700; color: var(--primary); font-size: 11px;">#${idx+1} [${escapeHtml(item.channel || '')}]</span>
                        <strong style="font-size: 12px; margin-left: 4px;">${escapeHtml(item.title || '')}</strong>
                        ${item.part_label ? `<span class="badge badge-info" style="font-size: 10px; margin-left: 4px;">${escapeHtml(item.part_label)}</span>` : ''}
                    </div>
                    <div style="font-size: 11px; color: var(--text-secondary);">
                        👤 @<strong>${escapeHtml(item.account_name || '')}</strong>
                    </div>
                </div>
            `).join('');
        }
    }

    // 6. Render Full Accounts Table Body
    const tableBody = document.getElementById('tab-autopilot-accounts-table-body');
    if (tableBody) {
        if (visibleAccounts.length === 0) {
            tableBody.innerHTML = `<tr><td colspan="7" class="table-empty"><i class="fa-solid fa-filter-circle-xmark"></i> Không tìm thấy tài khoản nào khớp với bộ lọc hoặc tìm kiếm.</td></tr>`;
            return;
        }

        let rowsHtml = '';
        visibleAccounts.forEach(acc => {
            const isSelected = selectedAutopilotAccounts.has(acc.name);
            const clipCount = acc.clips.length;
            const isExpanded = expandedAutopilotAccounts.has(acc.name);
            const safeAccId = acc.name.replace(/[^a-zA-Z0-9_-]/g, '_');

            // Main Row
            rowsHtml += `
                <tr class="acc-row-main ${isSelected ? 'is-selected' : ''}" data-acc-row="${escapeHtml(acc.name)}">
                    <td style="text-align: center;">
                        <label class="custom-checkbox custom-checkbox-inline" onclick="event.stopPropagation();">
                            <input type="checkbox" class="chk-autopilot-acc" data-acc="${escapeHtml(acc.name)}" ${isSelected ? 'checked' : ''}>
                            <span class="checkmark"></span>
                        </label>
                    </td>
                    <td>
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <div style="width: 28px; height: 28px; border-radius: 50%; background: rgba(255,255,255,0.06); border: 1px solid var(--border-color); display: flex; align-items: center; justify-content: center; font-size: 13px; color: var(--accent); flex-shrink: 0;">
                                <i class="fa-brands fa-tiktok"></i>
                            </div>
                            <div>
                                <strong style="font-size: 13px; color: var(--text-primary); cursor: pointer;" class="acc-name-clickable" data-acc="${escapeHtml(acc.name)}">@${escapeHtml(acc.name)}</strong>
                                ${acc.ads_id ? `<div style="font-size: 10px; color: var(--text-muted);"><i class="fa-solid fa-cube"></i> AdsPower: ${escapeHtml(acc.ads_id)}</div>` : ''}
                            </div>
                        </div>
                    </td>
                    <td>
                        <span class="badge badge-secondary" style="font-weight: 600; font-size: 11px;">
                            <i class="fa-solid fa-layer-group" style="font-size: 10px;"></i> ${escapeHtml(acc.group_name)}
                        </span>
                    </td>
                    <td>
                        ${acc.target_channel ? `
                            <span style="display: inline-flex; align-items: center; gap: 5px; font-size: 12px; font-weight: 600; color: var(--text-primary);">
                                <i class="fa-brands fa-youtube" style="color: #ef4444; font-size: 13px;"></i> ${escapeHtml(acc.target_channel)}
                            </span>
                        ` : `<span class="text-muted" style="font-size: 11px;">Chưa gán kênh</span>`}
                    </td>
                    <td>
                        ${clipCount > 0 ? `
                            <span class="badge badge-primary" style="font-size: 11.5px; font-weight: 700; padding: 3px 8px; display: inline-flex; align-items: center; gap: 5px;">
                                <i class="fa-solid fa-film"></i> ${clipCount} clip sẵn sàng
                            </span>
                        ` : `
                            <span class="badge badge-secondary" style="font-size: 11px; opacity: 0.75; display: inline-flex; align-items: center; gap: 4px;">
                                <i class="fa-solid fa-circle-check text-success"></i> 0 clip (Đã xong)
                            </span>
                        `}
                    </td>
                    <td style="text-align: center;">
                        <span class="badge badge-outline" style="font-weight: 700; font-size: 11px; letter-spacing: 0.5px;">${escapeHtml(acc.target_ip)}</span>
                    </td>
                    <td style="text-align: center;">
                        ${clipCount > 0 ? `
                            <button type="button" class="btn-toggle-row-clips" data-acc="${escapeHtml(acc.name)}" title="Xem danh sách clip của tài khoản này">
                                <span>${isExpanded ? 'Thu gọn' : `Xem ${clipCount} clip`}</span>
                                <i class="fa-solid ${isExpanded ? 'fa-chevron-up' : 'fa-chevron-down'}"></i>
                            </button>
                        ` : `
                            <span class="text-muted" style="font-size: 11px;">Trống</span>
                        `}
                    </td>
                </tr>
            `;

            // Subrow with Nested Clips Table
            if (clipCount > 0) {
                rowsHtml += `
                    <tr class="acc-subrow-clips ${isExpanded ? '' : 'is-collapsed'}" id="acc-subrow-${safeAccId}">
                        <td colspan="7">
                            <div class="nested-clips-box">
                                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; font-size: 12px; border-bottom: 1px solid var(--border-color); padding-bottom: 8px;">
                                    <span style="font-weight: 700; color: var(--text-primary); display: flex; align-items: center; gap: 6px;">
                                        <i class="fa-solid fa-list-check text-primary"></i> Hàng đợi video của <strong>@${escapeHtml(acc.name)}</strong> (${clipCount} video):
                                    </span>
                                    <span style="font-size: 11px; color: var(--text-secondary);">
                                        Nguồn: <strong>${escapeHtml(acc.target_channel)}</strong> &bull; IP: <strong>${escapeHtml(acc.target_ip)}</strong>
                                    </span>
                                </div>
                                <table class="nested-clips-table">
                                    <thead>
                                        <tr>
                                            <th width="40" style="text-align: center;">#</th>
                                            <th>Tiêu đề video</th>
                                            <th width="100">Phân đoạn</th>
                                            <th width="160">Thời gian tạo</th>
                                            <th width="110" style="text-align: center;">Thao tác</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        ${acc.clips.map((clip, cIdx) => `
                                            <tr>
                                                <td style="text-align: center; font-weight: 700; color: var(--text-secondary);">${cIdx + 1}</td>
                                                <td>
                                                    <div style="font-weight: 600; font-size: 12px; color: var(--text-primary);">${escapeHtml(clip.title || '')}</div>
                                                    <div style="font-size: 10.5px; color: var(--text-secondary); margin-top: 1px;">
                                                        <i class="fa-brands fa-youtube" style="color: #ef4444; font-size: 10px;"></i> ${escapeHtml(clip.channel || '')}
                                                    </div>
                                                </td>
                                                <td>
                                                    ${clip.part_label ? `<span class="badge badge-info" style="font-size: 10px;">${escapeHtml(clip.part_label)}</span>` : '<span class="text-muted" style="font-size: 10px;">Full</span>'}
                                                </td>
                                                <td style="font-size: 11px; color: var(--text-secondary);">
                                                    ${clip.created_at ? `<i class="fa-regular fa-clock" style="font-size: 10px;"></i> ${escapeHtml(clip.created_at)}` : '<span class="text-muted">Mới tạo</span>'}
                                                </td>
                                                <td style="text-align: center;">
                                                    <button type="button" class="btn btn-xs btn-outline-success btn-mark-queue-posted"
                                                            data-acc="${escapeHtml(clip.account_name || acc.name)}"
                                                            data-key="${escapeHtml(clip.clip_key || '')}"
                                                            data-chan="${escapeHtml(clip.channel || '')}"
                                                            data-title="${escapeHtml(clip.title || '')}"
                                                            data-part="${escapeHtml(clip.part_label || '')}"
                                                            title="Đánh dấu đã đăng & loại khỏi hàng đợi"
                                                            style="font-size: 10.5px; padding: 2px 7px; border-radius: 4px; font-weight: 700; display: inline-flex; align-items: center; gap: 3px; cursor: pointer;">
                                                        <i class="fa-solid fa-check"></i> Đã đăng
                                                    </button>
                                                </td>
                                            </tr>
                                        `).join('')}
                                    </tbody>
                                </table>
                            </div>
                        </td>
                    </tr>
                `;
            }
        });
        tableBody.innerHTML = rowsHtml;

        // Attach Checkbox event listeners
        tableBody.querySelectorAll('.chk-autopilot-acc').forEach(chk => {
            chk.addEventListener('change', () => {
                const acc = chk.getAttribute('data-acc');
                if (chk.checked) {
                    selectedAutopilotAccounts.add(acc);
                } else {
                    selectedAutopilotAccounts.delete(acc);
                }
                renderAutopilotUI();
            });
        });

        // Attach Toggle expand/collapse listeners
        const toggleAccordion = (acc) => {
            if (!acc) return;
            if (expandedAutopilotAccounts.has(acc)) {
                expandedAutopilotAccounts.delete(acc);
            } else {
                expandedAutopilotAccounts.add(acc);
            }
            renderAutopilotUI();
        };

        tableBody.querySelectorAll('.btn-toggle-row-clips').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                toggleAccordion(btn.getAttribute('data-acc'));
            });
        });

        tableBody.querySelectorAll('.acc-name-clickable').forEach(el => {
            el.addEventListener('click', (e) => {
                e.stopPropagation();
                toggleAccordion(el.getAttribute('data-acc'));
            });
        });

        // Attach Mark-as-posted listener
        tableBody.querySelectorAll('.btn-mark-queue-posted').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.stopPropagation();
                const acc = btn.getAttribute('data-acc');
                const key = btn.getAttribute('data-key');
                const chan = btn.getAttribute('data-chan');
                const title = btn.getAttribute('data-title');
                const part = btn.getAttribute('data-part');

                btn.disabled = true;
                btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';

                try {
                    const res = await fetch('/api/publishing/toggle_post', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            account_name: acc,
                            clip_key: key,
                            channel: chan,
                            title: title,
                            posted: true,
                            part_label: part || null
                        })
                    });
                    const data = await res.json();
                    if (data.success) {
                        pendingQueueRawCache = pendingQueueRawCache.filter(i =>
                            !(i.account_name === acc && i.channel === chan && i.title === title && (i.part_label || '') === (part || ''))
                        );
                        renderAutopilotUI();
                        showToast(`✅ Đã đánh dấu @${acc}: '${title}' (${part || 'Full'}) là ĐÃ ĐĂNG!`);
                    } else {
                        btn.disabled = false;
                        btn.innerHTML = '<i class="fa-solid fa-check"></i> Đã đăng';
                        showToast(`❌ Lỗi: ${data.error || 'Không thể lưu trạng thái'}`);
                    }
                } catch (err) {
                    btn.disabled = false;
                    btn.innerHTML = '<i class="fa-solid fa-check"></i> Đã đăng';
                    showToast(`❌ Lỗi kết nối: ${err.message}`);
                }
            });
        });
    }
}

let seenAutopilotLogKeys = new Set();
let lastAutopilotRunningState = false;

function appendAutopilotLog(msg, type = 'info') {
    const timeStr = new Date().toLocaleTimeString();
    const containers = [
        document.getElementById('terminal-logs-window'),
        document.getElementById('autopilot-logs')
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
        if (typeof terminalAutoScroll === 'undefined' || terminalAutoScroll) {
            container.scrollTop = container.scrollHeight;
        }
    });

    const term = document.getElementById('terminal-logs-window');
    const logsCountEl = document.getElementById('terminal-logs-count');
    if (logsCountEl && term) {
        logsCountEl.textContent = `${term.children.length} dòng`;
    }
}

function syncAutopilotLogsToTerminals(serverLogs) {
    if (!serverLogs || !serverLogs.length) return;
    const containers = [
        document.getElementById('terminal-logs-window'),
        document.getElementById('autopilot-logs')
    ];

    let hasNew = false;
    for (const raw of serverLogs) {
        if (!raw) continue;
        const key = raw.trim();
        if (seenAutopilotLogKeys.has(key)) continue;
        seenAutopilotLogKeys.add(key);
        hasNew = true;

        const clean = raw.replace(/^\[.*?\]\s*/, '');
        const timeMatch = raw.match(/^\[(.*?)\]/);
        const timeStr = timeMatch ? timeMatch[1] : new Date().toLocaleTimeString();

        let color = '#60a5fa';
        if (clean.includes('❌')) color = '#ef4444';
        else if (clean.includes('⚠️') || clean.includes('🎯')) color = '#f59e0b';
        else if (clean.includes('🎉') || clean.includes('🏁') || clean.includes('✅') || clean.includes('✨')) color = '#22c55e';

        containers.forEach(container => {
            if (!container) return;
            const logLine = document.createElement('div');
            logLine.className = 'log-line';
            logLine.style.color = color;
            logLine.textContent = `[${timeStr}] ${clean}`;
            container.appendChild(logLine);
        });
    }

    if (hasNew) {
        containers.forEach(container => {
            if (container && (typeof terminalAutoScroll === 'undefined' || terminalAutoScroll)) {
                container.scrollTop = container.scrollHeight;
            }
        });
        const term = document.getElementById('terminal-logs-window');
        const logsCountEl = document.getElementById('terminal-logs-count');
        if (logsCountEl && term) {
            logsCountEl.textContent = `${term.children.length} dòng`;
        }
    }
}

function setAutopilotRunningUI(isRunning) {
    isAutopilotRunning = isRunning;
    const btnStartModal = document.getElementById('btn-start-autopilot');
    const btnStopModal = document.getElementById('btn-stop-autopilot');
    const btnStartPage = document.getElementById('btn-page-start-autopilot');
    const btnStopPage = document.getElementById('btn-page-stop-autopilot');
    const statusBadgePage = document.getElementById('tab-autopilot-status-badge');
    const execBoxModal = document.getElementById('autopilot-execution-box');
    const miniBtn = document.getElementById('btn-autopilot-view-logs');

    if (isRunning) {
        if (execBoxModal) execBoxModal.classList.remove('hidden');
        if (btnStartModal) btnStartModal.classList.add('hidden');
        if (btnStopModal) btnStopModal.classList.remove('hidden');
        if (btnStartPage) btnStartPage.classList.add('hidden');
        if (btnStopPage) btnStopPage.classList.remove('hidden');
        if (statusBadgePage) {
            statusBadgePage.textContent = 'Đang chạy...';
            statusBadgePage.className = 'badge badge-primary';
        }
        if (miniBtn) {
            miniBtn.style.display = 'inline-flex';
            miniBtn.classList.remove('hidden');
        }
    } else {
        if (btnStartModal) btnStartModal.classList.remove('hidden');
        if (btnStopModal) btnStopModal.classList.add('hidden');
        if (btnStartPage) btnStartPage.classList.remove('hidden');
        if (btnStopPage) btnStopPage.classList.add('hidden');
        if (miniBtn) {
            miniBtn.style.display = 'none';
            miniBtn.classList.add('hidden');
        }
    }
}

function updateAutopilotProgressUI(data) {
    if (!data) return;

    const isRunning = Boolean(data.is_autopilot_running);
    setAutopilotRunningUI(isRunning);

    const percent = data.percentage || 0;
    const task = data.current_task || '';
    const autoState = data.autopilot_state || {};
    const successCount = autoState.success_count || 0;

    const miniProgress = document.getElementById('autopilot-mini-progress');
    if (miniProgress) miniProgress.textContent = `${percent}%`;

    const progressFill = document.getElementById('progress-fill');
    const progressPercent = document.getElementById('progress-percentage');
    const progressTask = document.getElementById('progress-current-task');
    if (isRunning) {
        if (progressFill) progressFill.style.width = `${percent}%`;
        if (progressPercent) progressPercent.textContent = `${percent}%`;
        if (progressTask) progressTask.textContent = task || 'Đang thực thi Auto-Pilot...';
    } else {
        if (percent >= 100 || successCount > 0) {
            if (progressFill) progressFill.style.width = '100%';
            if (progressPercent) progressPercent.textContent = '100%';
            if (progressTask) progressTask.textContent = task || 'Hoàn tất Auto-Pilot!';
        }
    }

    // Modal progress
    const modalBar = document.getElementById('autopilot-progress-bar');
    const modalPercent = document.getElementById('autopilot-progress-percent');
    const modalTask = document.getElementById('autopilot-current-task');
    if (modalBar) modalBar.style.width = `${percent}%`;
    if (modalPercent) modalPercent.textContent = `${percent}%`;
    if (modalTask) modalTask.textContent = task || (isRunning ? 'Đang xử lý...' : 'Hoàn tất');

    // Tự động reload hàng đợi khi chuyển trạng thái từ đang chạy sang đã chạy xong
    if (lastAutopilotRunningState && !isRunning) {
        if (typeof loadAutopilotQueue === 'function') {
            loadAutopilotQueue();
        }
        if (typeof fetchPublishingMatrix === 'function') {
            fetchPublishingMatrix();
        }
    }
    lastAutopilotRunningState = isRunning;

    if (data.logs && data.logs.length > 0) {
        syncAutopilotLogsToTerminals(data.logs);
    }
}

async function startAutopilotPipeline() {
    if (pendingQueueRawCache.length === 0) {
        await loadAutopilotQueue();
    }

    const allModels = buildAutopilotAccountsModel();
    if (!selectedAutopilotAccounts || selectedAutopilotAccounts.size === 0) {
        alert('⚠️ Vui lòng chọn ít nhất 1 tài khoản để bắt đầu Auto-Pilot!');
        return;
    }

    const selectedActiveAccs = allModels
        .filter(a => selectedAutopilotAccounts.has(a.name) && a.clips.length > 0)
        .map(a => a.name);

    if (selectedActiveAccs.length === 0) {
        alert('⚠️ Các tài khoản bạn chọn hiện tại không có clip nào sẵn sàng để đăng!\nVui lòng chọn các tài khoản có video (>0 clip).');
        return;
    }

    const optShutdown = (document.getElementById('autopilot-opt-shutdown')?.checked) ||
                        (document.getElementById('tab-opt-shutdown')?.checked) || false;

    // Reset log cache & clear terminals
    seenAutopilotLogKeys.clear();
    const modalLogs = document.getElementById('autopilot-logs');
    if (modalLogs) modalLogs.innerHTML = '';
    const mainTerm = document.getElementById('terminal-logs-window');
    if (mainTerm) {
        mainTerm.innerHTML = '<div class="log-line text-muted">[Auto-Pilot Console] Khởi tạo phiên làm việc mới...</div>';
    }

    setAutopilotRunningUI(true);

    appendAutopilotLog(`🚀 Bắt đầu quy trình Auto-Pilot Pipeline cho ${selectedActiveAccs.length} tài khoản đã chọn (${selectedActiveAccs.join(', ')})...`, 'info');

    try {
        const startRes = await fetch('/api/autopilot/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ accounts: selectedActiveAccs, auto_submit: true, auto_shutdown: optShutdown })
        });
        const startData = await startRes.json();
        if (!startData.success) {
            appendAutopilotLog(`❌ Không thể khởi chạy Auto-Pilot: ${startData.error}`, 'error');
            setAutopilotRunningUI(false);
            return;
        }
    } catch (e) {
        appendAutopilotLog(`❌ Lỗi kết nối tới máy chủ: ${e.message}`, 'error');
        setAutopilotRunningUI(false);
        return;
    }

    appendAutopilotLog('⚡ Auto-Pilot đã được chuyển giao cho máy chủ thực thi liên tục. Bạn có thể theo dõi chi tiết tại tab Logs...', 'success');

    if (typeof checkAndPollProgress === 'function') checkAndPollProgress();
    if (typeof startPollingProgress === 'function') startPollingProgress();
}

async function stopAutopilotPipeline() {
    autopilotCancelRequested = true;
    appendAutopilotLog('🛑 Đang gửi tín hiệu dừng pipeline...', 'warn');
    try {
        await fetch('/api/autopilot/stop', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
        await fetch('/api/pipeline/stop_batch', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
        await fetch('/api/system/cancel_shutdown', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
    } catch (e) {}

    setAutopilotRunningUI(false);
    const statusBadgePage = document.getElementById('tab-autopilot-status-badge');
    if (statusBadgePage) {
        statusBadgePage.textContent = 'Đã dừng';
        statusBadgePage.className = 'badge badge-warn';
    }
}

window.initAutoPilotHub = initAutoPilotHub;
window.loadAutopilotQueue = loadAutopilotQueue;
window.renderAutopilotUI = renderAutopilotUI;
window.startAutopilotPipeline = startAutopilotPipeline;
window.stopAutopilotPipeline = stopAutopilotPipeline;


/* ==========================================================================
   Download Video Pipeline (YouTube Videos & Shorts Scanner & Downloader)
   ========================================================================== */

let dlScannedData = {
    videos: [],
    shorts: [],
    channel_name: '',
    channel_url: ''
};
let dlActiveMediaTab = 'videos'; // 'videos' or 'shorts'
let dlSelectedItems = new Map(); // id -> item object
let dlIsScanning = false;
let dlPollInterval = null;
let dlWidgetIsExpanded = false;

function initDownloadVideoPipeline() {
    const channelSelect = document.getElementById('dl-channel-select');
    const customUrlInput = document.getElementById('dl-custom-url-input');
    const minViewsSelect = document.getElementById('dl-min-views-select');
    const maxDurationSelect = document.getElementById('dl-max-duration-select');
    const btnScan = document.getElementById('btn-dl-scan-channel');
    const btnRefreshScan = document.getElementById('dl-btn-refresh-scan');
    const searchInput = document.getElementById('dl-search-keyword');
    const tabBtnVideos = document.getElementById('dl-tab-btn-videos');
    const tabBtnShorts = document.getElementById('dl-tab-btn-shorts');
    const selectAllCheckbox = document.getElementById('dl-select-all-visible');
    const btnClearSelection = document.getElementById('dl-btn-clear-selection');
    const btnBatchStart = document.getElementById('btn-dl-batch-start');
    const btnOpenSourceDir = document.getElementById('btn-dl-open-source-dir');

    // 1. Channel select change
    if (channelSelect) {
        channelSelect.addEventListener('change', (e) => {
            const selectedVal = e.target.value;
            if (!selectedVal) {
                if (customUrlInput) customUrlInput.value = '';
                return;
            }
            const chan = (accountsData.youtube_channels || []).find(c => c.name === selectedVal || c.url === selectedVal);
            if (chan) {
                if (customUrlInput) customUrlInput.value = chan.url || '';
                const targetFolderLabel = document.getElementById('dl-target-folder-label');
                if (targetFolderLabel) {
                    targetFolderLabel.textContent = `input_sources/${chan.folder_name || chan.name}/`;
                }
                // Auto scan channel when selected
                scanYouTubeChannelMedia();
            }
        });
    }

    // 2. Scan button click
    if (btnScan) {
        btnScan.addEventListener('click', (e) => {
            e.preventDefault();
            scanYouTubeChannelMedia();
        });
    }
    if (btnRefreshScan) {
        btnRefreshScan.addEventListener('click', (e) => {
            e.preventDefault();
            scanYouTubeChannelMedia(true);
        });
    }

    // 3. Filter change events
    if (minViewsSelect) {
        minViewsSelect.addEventListener('change', () => {
            renderDownloadMediaCards();
        });
    }
    if (maxDurationSelect) {
        maxDurationSelect.addEventListener('change', () => {
            renderDownloadMediaCards();
        });
    }

    // 4. Keyword search input
    if (searchInput) {
        const debouncedDlSearch = debounce(() => {
            renderDownloadMediaCards();
        }, 100);

        searchInput.addEventListener('input', () => {
            debouncedDlSearch();
        });
    }

    // 5. Media Tab Switching (Videos vs Shorts)
    if (tabBtnVideos) {
        tabBtnVideos.addEventListener('click', () => {
            switchDownloadMediaTab('videos');
        });
    }
    if (tabBtnShorts) {
        tabBtnShorts.addEventListener('click', () => {
            switchDownloadMediaTab('shorts');
        });
    }

    // 6. Select All Visible
    if (selectAllCheckbox) {
        selectAllCheckbox.addEventListener('change', (e) => {
            const checked = e.target.checked;
            const currentList = getFilteredMediaList();
            const autoDownload = document.getElementById('dl-toggle-auto-download')?.checked ?? true;

            currentList.forEach(item => {
                if (checked) {
                    dlSelectedItems.set(item.id, item);
                } else {
                    dlSelectedItems.delete(item.id);
                }
            });
            updateDownloadSelectionUI();
            renderDownloadMediaCards();

            // If auto-download is enabled and user checked "Select All"
            if (checked && autoDownload && currentList.length > 0) {
                const unDownloaded = currentList.filter(it => !it.is_downloaded && it.status !== 'previously_downloaded' && it.status !== 'downloading' && it.status !== 'queued');
                if (unDownloaded.length > 0) {
                    triggerBatchDownload(unDownloaded);
                }
            }
        });
    }

    // 7. Clear selection
    if (btnClearSelection) {
        btnClearSelection.addEventListener('click', () => {
            dlSelectedItems.clear();
            if (selectAllCheckbox) selectAllCheckbox.checked = false;
            updateDownloadSelectionUI();
            renderDownloadMediaCards();
        });
    }

    // 8. Batch Download button
    if (btnBatchStart) {
        btnBatchStart.addEventListener('click', () => {
            const selectedArray = Array.from(dlSelectedItems.values());
            if (selectedArray.length === 0) {
                alert('Vui lòng tích chọn ít nhất 1 video để tải!');
                return;
            }
            triggerBatchDownload(selectedArray);
        });
    }

    // 9. Open Source Directory
    if (btnOpenSourceDir) {
        btnOpenSourceDir.addEventListener('click', async () => {
            const chanName = document.getElementById('dl-channel-select')?.value || '';
            const chan = (accountsData.youtube_channels || []).find(c => c.name === chanName);
            const folderName = chan ? (chan.folder_name || chan.name) : '';
            const baseSrc = accountsData.source_path || '';
            const targetPath = (baseSrc && folderName) ? `${baseSrc}/${folderName}` : (baseSrc || './input_sources');

            try {
                await fetch('/api/open_folder', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ path: targetPath })
                });
            } catch (e) {
                console.error(e);
            }
        });
    }

    // 10. Init Floating Bottom-Right Download Widget
    initFloatingDownloadWidget();

    // Populate channels dropdown initially
    populateDownloadChannelSelect();
    
    // Start global queue polling
    startDownloadQueuePolling();
}

function initFloatingDownloadWidget() {
    const miniPill = document.getElementById('dl-widget-minimized');
    const expandedCard = document.getElementById('dl-widget-expanded');
    const btnMinimize = document.getElementById('btn-dl-widget-minimize');
    const btnClear = document.getElementById('btn-dl-widget-clear');
    const btnOpenFolder = document.getElementById('btn-dl-widget-open-folder');

    if (miniPill) {
        miniPill.addEventListener('click', () => {
            dlWidgetIsExpanded = true;
            miniPill.classList.add('hidden');
            expandedCard?.classList.remove('hidden');
        });
    }

    if (btnMinimize) {
        btnMinimize.addEventListener('click', (e) => {
            e.stopPropagation();
            dlWidgetIsExpanded = false;
            expandedCard?.classList.add('hidden');
            miniPill?.classList.remove('hidden');
        });
    }

    if (btnClear) {
        btnClear.addEventListener('click', async (e) => {
            e.stopPropagation();
            try {
                await fetch('/api/youtube/clear_completed_queue', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: '{}'
                });
            } catch (err) {
                console.error('Error clearing queue:', err);
            }
        });
    }

    if (btnOpenFolder) {
        btnOpenFolder.addEventListener('click', async (e) => {
            e.stopPropagation();
            const baseSrc = accountsData.source_path || './input_sources';
            try {
                await fetch('/api/open_folder', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ path: baseSrc })
                });
            } catch (err) {
                console.error(err);
            }
        });
    }
}

function populateDownloadChannelSelect() {
    const channelSelect = document.getElementById('dl-channel-select');
    if (!channelSelect) return;

    const currentVal = channelSelect.value;
    channelSelect.innerHTML = '<option value="">-- Chọn kênh YouTube đã lưu --</option>';

    const channels = accountsData.youtube_channels || [];
    channels.forEach(c => {
        const opt = document.createElement('option');
        opt.value = c.name;
        opt.textContent = `${c.name} (${c.folder_name || c.name}) - ${c.total_downloaded || 0} clips`;
        channelSelect.appendChild(opt);
    });

    if (currentVal && channels.some(c => c.name === currentVal)) {
        channelSelect.value = currentVal;
    } else if (channels.length > 0 && !channelSelect.value) {
        channelSelect.value = channels[0].name;
        const customUrlInput = document.getElementById('dl-custom-url-input');
        if (customUrlInput) customUrlInput.value = channels[0].url || '';
        const targetFolderLabel = document.getElementById('dl-target-folder-label');
        if (targetFolderLabel) {
            targetFolderLabel.textContent = `input_sources/${channels[0].folder_name || channels[0].name}/`;
        }
    }
}

function switchDownloadMediaTab(tabType) {
    dlActiveMediaTab = tabType;
    const tabBtnVideos = document.getElementById('dl-tab-btn-videos');
    const tabBtnShorts = document.getElementById('dl-tab-btn-shorts');
    const containerVideos = document.getElementById('dl-container-videos');
    const containerShorts = document.getElementById('dl-container-shorts');

    if (tabType === 'videos') {
        tabBtnVideos?.classList.add('active');
        tabBtnShorts?.classList.remove('active');
        containerVideos?.classList.remove('hidden');
        containerShorts?.classList.add('hidden');
    } else {
        tabBtnVideos?.classList.remove('active');
        tabBtnShorts?.classList.add('active');
        containerVideos?.classList.add('hidden');
        containerShorts?.classList.remove('hidden');
    }

    renderDownloadMediaCards();
}

async function scanYouTubeChannelMedia(forceRefresh = false) {
    const customUrlInput = document.getElementById('dl-custom-url-input');
    const channelSelect = document.getElementById('dl-channel-select');
    const minViewsSelect = document.getElementById('dl-min-views-select');
    const maxDurationSelect = document.getElementById('dl-max-duration-select');

    let channelUrl = customUrlInput?.value.trim() || '';
    const channelName = channelSelect?.value || '';

    if (!channelUrl && channelName) {
        const chan = (accountsData.youtube_channels || []).find(c => c.name === channelName);
        if (chan) channelUrl = chan.url || '';
    }

    if (!channelUrl) {
        alert('Vui lòng chọn kênh hoặc nhập URL / @Handle kênh YouTube!');
        return;
    }

    const minViews = parseInt(minViewsSelect?.value || '0', 10);
    const maxDuration = parseInt(maxDurationSelect?.value || '0', 10);

    const gridVideos = document.getElementById('dl-grid-videos');
    const gridShorts = document.getElementById('dl-grid-shorts');

    const loadingHtml = `
        <div class="dl-empty-state" style="grid-column: 1 / -1;">
            <i class="fa-solid fa-circle-notch fa-spin text-danger" style="font-size: 44px; margin-bottom: 14px; color: #ef4444;"></i>
            <h3>Đang quét dữ liệu từ YouTube...</h3>
            <p>Hệ thống đang trích xuất đồng thời danh sách Video dài và Shorts theo thời gian thực. Vui lòng chờ vài giây...</p>
        </div>
    `;

    if (gridVideos) gridVideos.innerHTML = loadingHtml;
    if (gridShorts) gridShorts.innerHTML = loadingHtml;

    dlIsScanning = true;
    const btnScan = document.getElementById('btn-dl-scan-channel');
    if (btnScan) {
        btnScan.disabled = true;
        btnScan.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Đang Quét...';
    }

    try {
        const srcPath = accountsData.source_path || '';
        const destPath = accountsData.dest_path || '';
        const refreshParam = forceRefresh ? '&refresh=1' : '';
        const queryUrl = `/api/youtube/scan_channel_media?url=${encodeURIComponent(channelUrl)}&name=${encodeURIComponent(channelName)}&min_views=${minViews}&max_duration=${maxDuration}&source=${encodeURIComponent(srcPath)}&dest=${encodeURIComponent(destPath)}${refreshParam}`;
        
        const res = await fetch(queryUrl);
        const data = await res.json();

        if (data.success) {
            dlScannedData = {
                videos: data.videos || [],
                shorts: data.shorts || [],
                channel_name: data.channel_name || channelName,
                channel_url: data.channel_url || channelUrl
            };

            const countVideosBadge = document.getElementById('dl-count-videos-badge');
            const countShortsBadge = document.getElementById('dl-count-shorts-badge');
            if (countVideosBadge) countVideosBadge.textContent = dlScannedData.videos.length;
            if (countShortsBadge) countShortsBadge.textContent = dlScannedData.shorts.length;

            renderDownloadMediaCards();
        } else {
            const errorHtml = `
                <div class="dl-empty-state" style="grid-column: 1 / -1; border-color: rgba(239, 68, 68, 0.4);">
                    <i class="fa-solid fa-triangle-exclamation text-danger" style="font-size: 44px; margin-bottom: 14px; color: #ef4444;"></i>
                    <h3 style="color: #ef4444;">Không thể quét kênh YouTube</h3>
                    <p>${data.error || 'Vui lòng kiểm tra lại URL kênh YouTube hoặc kết nối mạng của bạn.'}</p>
                </div>
            `;
            if (gridVideos) gridVideos.innerHTML = errorHtml;
            if (gridShorts) gridShorts.innerHTML = errorHtml;
        }
    } catch (err) {
        console.error('Error scanning channel:', err);
    } finally {
        dlIsScanning = false;
        if (btnScan) {
            btnScan.disabled = false;
            btnScan.innerHTML = '<i class="fa-solid fa-magnifying-glass"></i> Quét Kênh YouTube';
        }
    }
}

function getFilteredMediaList() {
    const rawList = dlActiveMediaTab === 'videos' ? dlScannedData.videos : dlScannedData.shorts;
    const searchKeyword = (document.getElementById('dl-search-keyword')?.value || '').toLowerCase().trim();
    const minViews = parseInt(document.getElementById('dl-min-views-select')?.value || '0', 10);
    const maxDuration = parseInt(document.getElementById('dl-max-duration-select')?.value || '0', 10);

    return rawList.filter(item => {
        if (searchKeyword && !item.title.toLowerCase().includes(searchKeyword)) {
            return false;
        }
        if (minViews > 0 && item.views < minViews) {
            return false;
        }
        if (dlActiveMediaTab === 'videos' && maxDuration > 0 && item.duration > maxDuration) {
            return false;
        }
        return true;
    });
}

function renderDownloadMediaCards() {
    const container = dlActiveMediaTab === 'videos' 
        ? document.getElementById('dl-grid-videos') 
        : document.getElementById('dl-grid-shorts');
    if (!container) return;

    const list = getFilteredMediaList();

    if (list.length === 0) {
        container.innerHTML = `
            <div class="dl-empty-state">
                <i class="fa-solid fa-magnifying-glass" style="font-size: 44px; color: var(--text-muted); margin-bottom: 12px;"></i>
                <h3>Không tìm thấy ${dlActiveMediaTab === 'videos' ? 'video' : 'shorts'} nào phù hợp</h3>
                <p>Thử thay đổi bộ lọc lượt xem, thời lượng hoặc từ khóa tìm kiếm.</p>
            </div>
        `;
        return;
    }

    container.innerHTML = '';
    const fragment = document.createDocumentFragment();

    list.forEach(item => {
        const isSelected = dlSelectedItems.has(item.id);
        const isCurrentDl = item.is_downloaded || item.status === 'downloaded';
        const isPrevDl = item.status === 'previously_downloaded' || item.is_previously_downloaded;

        const card = document.createElement('div');
        card.className = `dl-video-card ${isSelected ? 'is-selected' : ''} ${isCurrentDl ? 'is-downloaded' : ''} ${isPrevDl ? 'is-previously-downloaded' : ''}`;
        card.dataset.id = item.id;
        card.dataset.url = item.url;

        const isShort = Boolean(item.is_short || (item.duration > 0 && item.duration < 120));
        const isLong = Boolean(item.is_long || (item.duration && item.duration > 900));
        const thumbAspectClass = isShort ? 'short-aspect' : '';

        let statusBadgeHtml = '';
        if (item.status === 'downloading') {
            statusBadgeHtml = `<span class="dl-card-status-badge downloading"><i class="fa-solid fa-circle-notch fa-spin"></i> Đang tải...</span>`;
        } else if (item.status === 'queued') {
            statusBadgeHtml = `<span class="dl-card-status-badge" style="background: rgba(148, 163, 184, 0.15); color: var(--text-secondary);"><i class="fa-solid fa-clock"></i> Chờ tải...</span>`;
        } else if (isCurrentDl) {
            statusBadgeHtml = `<span class="dl-card-status-badge downloaded"><i class="fa-solid fa-circle-check"></i> Đã có trong kho</span>`;
        } else if (isPrevDl) {
            statusBadgeHtml = `<span class="dl-card-status-badge previously-downloaded"><i class="fa-solid fa-clock-rotate-left"></i> Đã từng tải</span>`;
        } else {
            statusBadgeHtml = `<span class="dl-card-status-badge ready"><i class="fa-solid fa-cloud-arrow-down"></i> Sẵn sàng tải</span>`;
        }

        let btnActionHtml = '';
        if (isCurrentDl) {
            btnActionHtml = `
                <button type="button" class="btn btn-xs btn-secondary btn-dl-single" style="font-weight: 700;">
                    <i class="fa-solid fa-arrows-rotate"></i> 
                    <span>Tải Lại</span>
                </button>
            `;
        } else if (isPrevDl) {
            btnActionHtml = `
                <button type="button" class="btn btn-xs btn-prev-dl btn-dl-single" style="font-weight: 700; background: rgba(245, 158, 11, 0.15); color: #f59e0b; border: 1px solid rgba(245, 158, 11, 0.35);">
                    <i class="fa-solid fa-clock-rotate-left"></i> 
                    <span>Tải Lại</span>
                </button>
            `;
        } else {
            btnActionHtml = `
                <button type="button" class="btn btn-xs btn-primary btn-dl-single" style="font-weight: 700;">
                    <i class="fa-solid fa-cloud-arrow-down"></i> 
                    <span>Tải Xuống</span>
                </button>
            `;
        }

        card.innerHTML = `
            <div class="dl-card-thumb-wrap ${thumbAspectClass}">
                <img src="${item.thumbnail}" class="dl-card-thumb" alt="${item.title}" loading="lazy" onerror="this.src='https://i.ytimg.com/vi/${item.id}/hqdefault.jpg'">
                
                <label class="dl-card-checkbox-overlay" title="Tích chọn video">
                    <input type="checkbox" class="dl-card-checkbox" ${isSelected ? 'checked' : ''}>
                </label>

                ${isShort ? `
                    <div class="dl-card-short-tag" title="Video ngắn dưới 2 phút (<120s)">
                        <i class="fa-solid fa-bolt"></i>
                        <span>SHORT</span>
                    </div>
                ` : (isLong ? `
                    <div class="dl-card-long-tag" title="Video dài trên 15 phút (>15p)">
                        <i class="fa-solid fa-film"></i>
                        <span>LONG</span>
                    </div>
                ` : '')}

                <div class="dl-card-duration-badge ${isShort ? 'is-short-duration' : (isLong ? 'is-long-duration' : '')}">
                    <i class="fa-solid ${isShort ? 'fa-bolt text-warning' : (isLong ? 'fa-film text-info' : 'fa-clock')}"></i>
                    <span>${item.formatted_duration || '0:00'}</span>
                </div>
            </div>

            <div class="dl-card-body">
                <h4 class="dl-card-title" title="${item.title}">${item.title}</h4>

                <div class="dl-card-meta">
                    <div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">
                        <div class="dl-views-pill" title="${item.views.toLocaleString()} views">
                            <i class="fa-solid fa-fire"></i>
                            <span>${item.formatted_views || '0 views'}</span>
                        </div>
                        ${isShort ? `<span class="dl-meta-short-badge" title="Video ngắn dưới 2 phút"><i class="fa-solid fa-bolt"></i> Short</span>` : ''}
                        ${isLong ? `<span class="dl-meta-long-badge" title="Video dài trên 15 phút"><i class="fa-solid fa-film"></i> Long</span>` : ''}
                    </div>
                    ${statusBadgeHtml}
                </div>
            </div>

            <div class="dl-card-progress ${item.status === 'downloading' ? '' : 'hidden'}">
                <div class="dl-card-progress-bar" style="width: ${item.progress_percent || 0}%;"></div>
            </div>

            <div class="dl-card-footer">
                ${btnActionHtml}
                <a href="${item.url}" target="_blank" class="btn btn-xs btn-outline" title="Mở video trên YouTube" style="display: inline-flex; align-items: center; gap: 4px;">
                    <i class="fa-brands fa-youtube text-danger"></i> YouTube
                </a>
            </div>
        `;

        // Checkbox event listener (AUTO DOWNLOAD QUEUE TRIGGER)
        const checkbox = card.querySelector('.dl-card-checkbox');
        checkbox.addEventListener('change', (e) => {
            const isChecked = e.target.checked;
            if (isChecked) {
                dlSelectedItems.set(item.id, item);
                card.classList.add('is-selected');

                // Check if auto-download toggle is active
                const autoDownload = document.getElementById('dl-toggle-auto-download')?.checked ?? true;
                if (autoDownload && !isCurrentDl && !isPrevDl && item.status !== 'downloading' && item.status !== 'queued') {
                    triggerSingleVideoDownload(item, card);
                }
            } else {
                dlSelectedItems.delete(item.id);
                card.classList.remove('is-selected');
            }
            updateDownloadSelectionUI();
        });

        // Single download button click
        const btnSingle = card.querySelector('.btn-dl-single');
        btnSingle.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            triggerSingleVideoDownload(item, card);
        });

        fragment.appendChild(card);
    });

    container.appendChild(fragment);

    updateDownloadSelectionUI();
}

function updateDownloadSelectionUI() {
    const counter = document.getElementById('dl-selected-counter');
    const btnBatchCount = document.getElementById('dl-btn-batch-count');
    const count = dlSelectedItems.size;

    if (counter) counter.textContent = count;
    if (btnBatchCount) btnBatchCount.textContent = count;
}

async function triggerSingleVideoDownload(item, cardEl) {
    if (!item || !item.url) return;

    item.status = 'queued';
    item.progress_percent = 0;
    
    // Update card UI immediately to Queued state
    if (cardEl) {
        const statusBadge = cardEl.querySelector('.dl-card-status-badge');
        if (statusBadge) {
            statusBadge.className = 'dl-card-status-badge';
            statusBadge.style.background = 'rgba(148, 163, 184, 0.15)';
            statusBadge.style.color = 'var(--text-secondary)';
            statusBadge.innerHTML = '<i class="fa-solid fa-clock"></i> Chờ tải...';
        }
    }

    const isShortFlag = Boolean(item.is_short || (item.duration > 0 && item.duration < 120));
    const payload = {
        url: item.url,
        title: item.title,
        channel: item.channel || dlScannedData.channel_name || 'Downloads',
        is_short: isShortFlag,
        thumbnail: item.thumbnail || '',
        source_dir: accountsData.source_path || ''
    };

    try {
        const res = await fetch('/api/youtube/download_item', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        await res.json();
    } catch (e) {
        console.error('Error adding to download queue:', e);
    }
}

async function triggerBatchDownload(items) {
    if (!items || items.length === 0) return;

    const payload = {
        items: items.map(item => ({
            url: item.url,
            title: item.title,
            channel: item.channel || dlScannedData.channel_name || 'Downloads',
            is_short: Boolean(item.is_short || (item.duration > 0 && item.duration < 120)),
            thumbnail: item.thumbnail || ''
        })),
        source_dir: accountsData.source_path || ''
    };

    // Mark all as queued in UI
    items.forEach(it => {
        it.status = 'queued';
        it.progress_percent = 0;
    });
    renderDownloadMediaCards();

    try {
        const res = await fetch('/api/youtube/download_batch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        await res.json();
    } catch (e) {
        console.error('Error starting batch download:', e);
    }
}

function startDownloadQueuePolling() {
    if (dlPollInterval) return;

    dlPollInterval = setInterval(async () => {
        try {
            const res = await fetch('/api/youtube/download_queue');
            const data = await res.json();
            const tasks = data.tasks || [];
            const activeCount = data.active_count || 0;
            const queuedCount = data.queued_count || 0;
            const completedCount = data.completed_count || 0;
            const totalRemaining = activeCount + queuedCount;

            const floatingWidget = document.getElementById('floating-download-widget');
            const miniPill = document.getElementById('dl-widget-minimized');
            const expandedCard = document.getElementById('dl-widget-expanded');
            const miniTitle = document.getElementById('dl-widget-mini-title');
            const miniStatus = document.getElementById('dl-widget-mini-status');
            const activeBadge = document.getElementById('dl-widget-active-badge');
            const queueList = document.getElementById('dl-widget-queue-list');
            const footerSummary = document.getElementById('dl-widget-footer-summary');

            if (tasks.length > 0) {
                if (floatingWidget) floatingWidget.classList.remove('hidden');

                // Active downloading task (if any)
                const currentTask = tasks.find(t => t.status === 'downloading' || t.status === 'processing');
                
                if (miniTitle) {
                    miniTitle.textContent = currentTask ? currentTask.title : (totalRemaining > 0 ? 'Đang chuẩn bị tải...' : 'Tải hoàn tất!');
                }
                if (miniStatus) {
                    if (currentTask) {
                        miniStatus.textContent = `Đang tải: ${currentTask.progress_percent || 0}% (${currentTask.speed_str || ''}) | Còn ${queuedCount} clip`;
                    } else if (totalRemaining > 0) {
                        miniStatus.textContent = `${queuedCount} clip đang chờ trong hàng đợi...`;
                    } else {
                        miniStatus.textContent = `Đã hoàn tất ${completedCount} clip`;
                    }
                }
                if (activeBadge) {
                    activeBadge.textContent = `${totalRemaining} clip`;
                    if (totalRemaining > 0) {
                        activeBadge.className = 'badge-count';
                        activeBadge.style.background = 'linear-gradient(135deg, #ef4444, #f97316)';
                    } else {
                        activeBadge.className = 'badge-count badge-success';
                        activeBadge.style.background = 'linear-gradient(135deg, #10b981, #059669)';
                    }
                }
                if (footerSummary) {
                    footerSummary.textContent = `${completedCount} hoàn tất | ${queuedCount} chờ tải`;
                }

                // Render list in expanded panel
                if (queueList) {
                    queueList.innerHTML = tasks.map((t, idx) => {
                        const isDownloading = t.status === 'downloading' || t.status === 'processing';
                        const isQueued = t.status === 'queued';
                        const isCompleted = t.status === 'completed';
                        const isError = t.status === 'error';

                        let statusBadge = '';
                        let itemClass = '';
                        if (isDownloading) {
                            itemClass = 'is-downloading';
                            statusBadge = `<span style="color: #f97316; font-size: 11px; font-weight: 700;"><i class="fa-solid fa-circle-notch fa-spin"></i> ${t.progress_percent || 0}% (${t.speed_str || ''})</span>`;
                        } else if (isQueued) {
                            statusBadge = `<span style="color: var(--text-muted); font-size: 11px; font-weight: 600;"><i class="fa-solid fa-clock"></i> Chờ tải (#${idx + 1})</span>`;
                        } else if (isCompleted) {
                            itemClass = 'is-completed';
                            statusBadge = `<span style="color: #22c55e; font-size: 11px; font-weight: 700;"><i class="fa-solid fa-circle-check"></i> Đã xong (${t.size_mb || 0} MB)</span>`;
                        } else if (isError) {
                            statusBadge = `<span style="color: #ef4444; font-size: 11px; font-weight: 700;"><i class="fa-solid fa-circle-xmark"></i> Lỗi tải</span>`;
                        }

                        return `
                            <div class="dl-widget-item ${itemClass}">
                                <div class="dl-widget-item-top">
                                    <span class="dl-widget-item-title" title="${t.title}">
                                        ${t.is_short ? '<i class="fa-solid fa-bolt" style="color: #f59e0b;" title="Short (<2p)"></i> ' : (t.is_long ? '<i class="fa-solid fa-film" style="color: #6366f1;" title="Long (>15p)"></i> ' : '<i class="fa-solid fa-video" style="color: #3b82f6;"></i> ')}${t.title}
                                    </span>
                                    <span class="dl-widget-item-channel">${t.channel || 'Video'}</span>
                                </div>
                                <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 2px;">
                                    ${statusBadge}
                                    <span style="font-size: 10px; color: var(--text-muted);">${t.eta_str && isDownloading ? `còn ~${t.eta_str}` : ''}</span>
                                </div>
                                ${isDownloading ? `
                                    <div class="dl-card-progress" style="margin-top: 4px; border-radius: 4px; overflow: hidden; height: 4px;">
                                        <div class="dl-card-progress-bar" style="width: ${t.progress_percent || 0}%;"></div>
                                    </div>
                                ` : ''}
                            </div>
                        `;
                    }).join('');
                }

                // Update cards status in active list on the page if visible
                tasks.forEach(t => {
                    const card = document.querySelector(`.dl-video-card[data-url="${t.url}"]`);
                    if (card) {
                        const statusBadge = card.querySelector('.dl-card-status-badge');
                        const progressBar = card.querySelector('.dl-card-progress');
                        const progressBarFill = card.querySelector('.dl-card-progress-bar');

                        if (t.status === 'completed') {
                            card.classList.add('is-downloaded');
                            if (statusBadge) {
                                statusBadge.className = 'dl-card-status-badge downloaded';
                                statusBadge.innerHTML = '<i class="fa-solid fa-circle-check"></i> Đã có trong kho';
                            }
                            if (progressBar) progressBar.classList.add('hidden');
                        } else if (t.status === 'downloading' || t.status === 'processing') {
                            if (statusBadge) {
                                statusBadge.className = 'dl-card-status-badge downloading';
                                statusBadge.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin"></i> ${t.progress_percent || 0}% (${t.speed_str || ''})`;
                            }
                            if (progressBar) progressBar.classList.remove('hidden');
                            if (progressBarFill) progressBarFill.style.width = `${t.progress_percent || 0}%`;
                        } else if (t.status === 'queued') {
                            if (statusBadge) {
                                statusBadge.className = 'dl-card-status-badge';
                                statusBadge.style.background = 'rgba(148, 163, 184, 0.15)';
                                statusBadge.style.color = 'var(--text-secondary)';
                                statusBadge.innerHTML = '<i class="fa-solid fa-clock"></i> Chờ tải...';
                            }
                        }
                    }
                });
            } else {
                if (floatingWidget) floatingWidget.classList.add('hidden');
            }
        } catch (e) {
            console.error('Error polling queue:', e);
        }
    }, 1200);
}

function onDownloadTabActivated() {
    populateDownloadChannelSelect();
    const chanSelect = document.getElementById('dl-channel-select');
    if (chanSelect && chanSelect.value && (!dlScannedData.videos.length && !dlScannedData.shorts.length)) {
        scanYouTubeChannelMedia();
    }
}

window.initDownloadVideoPipeline = initDownloadVideoPipeline;
window.populateDownloadChannelSelect = populateDownloadChannelSelect;
window.scanYouTubeChannelMedia = scanYouTubeChannelMedia;
window.switchDownloadMediaTab = switchDownloadMediaTab;
window.onDownloadTabActivated = onDownloadTabActivated;
window.initFloatingDownloadWidget = initFloatingDownloadWidget;

/* ==========================================================================
   TIKTOK CREATOR ANALYTICS & DASHBOARD ENGINE
   ========================================================================== */
let analyticsPollingInterval = null;

async function loadAnalyticsData() {
    try {
        const res = await fetch('/api/analytics/data');
        if (!res.ok) return;
        const json = await res.json();
        if (json.success) {
            renderAnalyticsDashboard(json.data, json.current_ip);
        }
    } catch (e) {
        console.error('Error loading analytics:', e);
    }
}

function renderAnalyticsDashboard(data, ipInfo) {
    // 1. Cập nhật IP Safety Badge
    const ipBadge = document.getElementById('analytics-ip-badge');
    const ipText = document.getElementById('analytics-ip-text');
    if (ipBadge && ipText && ipInfo) {
        if (ipInfo.is_vn) {
            ipBadge.style.background = 'rgba(239, 68, 68, 0.15)';
            ipBadge.style.border = '1px solid rgba(239, 68, 68, 0.4)';
            ipBadge.style.color = '#ef4444';
            ipText.innerHTML = `<span style="width: 8px; height: 8px; border-radius: 50%; background: #ef4444; display: inline-block;"></span> ⚠️ IP: ${ipInfo.ip} (${ipInfo.country}) - <b style="color:#ff4d4f">CẢNH BÁO IP VN!</b>`;
        } else {
            ipBadge.style.background = 'rgba(16, 185, 129, 0.15)';
            ipBadge.style.border = '1px solid rgba(16, 185, 129, 0.4)';
            ipBadge.style.color = '#10b981';
            ipText.innerHTML = `<span style="width: 8px; height: 8px; border-radius: 50%; background: #10b981; display: inline-block;"></span> 🛡️ IP: ${ipInfo.ip} (${ipInfo.country}) - <b>Clean Non-VN IP</b>`;
        }
    }

    // 2. Cập nhật các thẻ KPI tổng quan
    const overall = (data && data.overall) || {};
    const totalViewsEl = document.getElementById('kpi-total-views');
    const totalFollowersEl = document.getElementById('kpi-total-followers');
    const totalLikesEl = document.getElementById('kpi-total-likes');
    const totalCommentsEl = document.getElementById('kpi-total-comments');
    const avgCompletionEl = document.getElementById('kpi-avg-completion');

    if (totalViewsEl) totalViewsEl.textContent = (overall.total_views || 0).toLocaleString();
    if (totalFollowersEl) totalFollowersEl.textContent = (overall.total_followers || 0).toLocaleString();
    if (totalLikesEl) totalLikesEl.textContent = (overall.total_likes || 0).toLocaleString();
    if (totalCommentsEl) totalCommentsEl.textContent = (overall.total_comments || 0).toLocaleString();
    if (avgCompletionEl) avgCompletionEl.textContent = overall.avg_completion_rate || '0%';

    // 3. Cập nhật bảng chi tiết từng kênh TikTok
    const tbody = document.getElementById('analytics-table-body');
    if (!tbody) return;

    const accountsObj = (data && data.accounts) || {};
    const accountsList = (accountsData && accountsData.tiktok_accounts) || [];
    
    if (accountsList.length === 0 && Object.keys(accountsObj).length === 0) {
        tbody.innerHTML = `<tr><td colspan="10" class="table-empty"><i class="fa-brands fa-tiktok"></i> Chưa có tài khoản TikTok nào được cấu hình trong hệ thống.</td></tr>`;
        return;
    }

    let rowsHtml = '';
    let idx = 1;

    accountsList.forEach(acc => {
        const accKey = String(acc.id || acc.adspower_id || acc.channel_name);
        const stat = accountsObj[accKey] || {};
        const isSuccess = stat.success === true;
        const channelName = acc.channel_name || acc.name || 'TikTok Channel';
        const accountHandle = acc.account_name || acc.name || '@channel';
        const adspowerProfile = acc.adspower_id || acc.serial_number || 'N/A';
        
        const views = isSuccess ? (stat.video_views_7d || 0).toLocaleString() : '--';
        const followers = isSuccess ? (stat.followers_total || 0).toLocaleString() : '--';
        const likes = isSuccess ? (stat.likes_total || 0).toLocaleString() : '--';
        const comments = isSuccess ? (stat.comments_total || 0).toLocaleString() : '--';
        const completionRate = isSuccess ? (stat.avg_completion_rate || '--') : '--';
        const lastUpdated = stat.last_updated || (stat.last_attempt ? `<span style="color:#ef4444">${stat.last_attempt} (Lỗi)</span>` : '<span style="color:var(--text-muted)">Chưa thu thập</span>');
        
        const proxyLoc = acc.build_up_ip || acc.original_ip || 'Non-VN';

        rowsHtml += `
            <tr>
                <td style="text-align: center; color: var(--text-muted);">${idx++}</td>
                <td>
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <div style="width: 32px; height: 32px; border-radius: 50%; background: linear-gradient(135deg, #00f2fe, #4facfe); display: flex; align-items: center; justify-content: center; color: #000; font-weight: 700; font-size: 14px;">
                            ${channelName.charAt(0).toUpperCase()}
                        </div>
                        <div>
                            <div style="font-weight: 700; color: var(--text-primary);">${channelName}</div>
                            <div style="font-size: 11px; color: var(--text-muted);">${accountHandle.startsWith('@') ? accountHandle : '@' + accountHandle}</div>
                        </div>
                    </div>
                </td>
                <td>
                    <span class="badge" style="background: rgba(255,255,255,0.06); border: 1px solid var(--border-color); font-size: 11px; padding: 4px 8px; border-radius: 4px;">
                        <i class="fa-solid fa-window-maximize" style="color:#00f2fe"></i> ${adspowerProfile} (${proxyLoc})
                    </span>
                </td>
                <td style="text-align: right; font-weight: 700; color: #00f2fe;">${followers}</td>
                <td style="text-align: right; font-weight: 700; color: #10b981;">${views}</td>
                <td style="text-align: right; font-weight: 600; color: #ff0050;">${likes}</td>
                <td style="text-align: right; font-weight: 600; color: #f59e0b;">${comments}</td>
                <td style="text-align: center;">
                    <span style="display: inline-block; padding: 2px 8px; border-radius: 12px; font-weight: 700; font-size: 11px; background: rgba(0, 242, 254, 0.1); color: #00f2fe; border: 1px solid rgba(0, 242, 254, 0.3);">
                        ${completionRate}
                    </span>
                </td>
                <td style="text-align: center; font-size: 11px;">${lastUpdated}</td>
                <td style="text-align: center;">
                    <button class="btn btn-sm" onclick="triggerSingleCollectAnalytics('${acc.id || acc.adspower_id || acc.channel_name}')" style="padding: 4px 10px; font-size: 11px; border-radius: 4px; background: rgba(255,255,255,0.05); border: 1px solid var(--border-color); cursor: pointer; color: var(--text-primary); transition: var(--transition);">
                        <i class="fa-solid fa-arrows-rotate"></i> Sync
                    </button>
                </td>
            </tr>
        `;
    });

    tbody.innerHTML = rowsHtml;
}

async function triggerCollectAnalytics() {
    const btn = document.getElementById('btn-collect-analytics');
    const progressBox = document.getElementById('analytics-collect-progress');
    const logBox = document.getElementById('analytics-live-log');
    
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> <span>Collecting...</span>';
    }
    if (progressBox) progressBox.style.display = 'block';
    if (logBox) logBox.innerHTML = '<div style="color: #00f2fe;">[Bắt đầu] Đang kết nối AdsPower API và kiểm tra IP an toàn...</div>';

    try {
        const res = await fetch('/api/analytics/collect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: '{}'
        });
        const json = await res.json();
        if (!json.success) {
            alert('⚠️ ' + (json.error || 'Không thể bắt đầu thu thập'));
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '<i class="fa-solid fa-cloud-arrow-down"></i> <span>Collect Data</span>';
            }
            if (progressBox) progressBox.style.display = 'none';
            return;
        }

        startAnalyticsPolling();

    } catch (e) {
        console.error(e);
        alert('Lỗi kết nối máy chủ!');
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="fa-solid fa-cloud-arrow-down"></i> <span>Collect Data</span>';
        }
    }
}

async function triggerSingleCollectAnalytics(accId) {
    try {
        const res = await fetch('/api/analytics/collect_single', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ account_id: accId })
        });
        const json = await res.json();
        if (json.success) {
            const progressBox = document.getElementById('analytics-collect-progress');
            if (progressBox) progressBox.style.display = 'block';
            startAnalyticsPolling();
        } else {
            alert('⚠️ ' + (json.error || 'Lỗi'));
        }
    } catch (e) {
        console.error(e);
    }
}

function startAnalyticsPolling() {
    if (analyticsPollingInterval) clearInterval(analyticsPollingInterval);
    const progressBox = document.getElementById('analytics-collect-progress');
    const logBox = document.getElementById('analytics-live-log');
    const btn = document.getElementById('btn-collect-analytics');

    analyticsPollingInterval = setInterval(async () => {
        try {
            const res = await fetch('/api/analytics/status');
            if (!res.ok) return;
            const statusJson = await res.json();
            
            if (logBox && statusJson.progress_log) {
                logBox.innerHTML = statusJson.progress_log.map(l => `<div>${l}</div>`).join('');
                logBox.scrollTop = logBox.scrollHeight;
            }

            if (!statusJson.is_collecting) {
                clearInterval(analyticsPollingInterval);
                analyticsPollingInterval = null;
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = '<i class="fa-solid fa-cloud-arrow-down"></i> <span>Collect Data</span>';
                }
                setTimeout(() => {
                    if (progressBox) progressBox.style.display = 'none';
                }, 4000);
                loadAnalyticsData();
            }
        } catch (e) {
            console.error('Polling error:', e);
        }
    }, 1500);
}

function initTikTokAnalyticsEngine() {
    const btnCollect = document.getElementById('btn-collect-analytics');
    if (btnCollect) {
        btnCollect.addEventListener('click', triggerCollectAnalytics);
    }
    loadAnalyticsData();
}

window.triggerSingleCollectAnalytics = triggerSingleCollectAnalytics;
window.triggerCollectAnalytics = triggerCollectAnalytics;
window.loadAnalyticsData = loadAnalyticsData;
window.initTikTokAnalyticsEngine = initTikTokAnalyticsEngine;






// Heartbeat System to keep background server alive
setInterval(() => { fetch('/api/heartbeat').catch(e => {}); }, 10000);

/* ==========================================================================
   Logs Console Manager & Interactive Tools (Copy, Clear, Auto-Scroll)
   ========================================================================== */
let terminalAutoScroll = true;

function initLogsControls() {
    const btnCopy = document.getElementById('btn-copy-terminal-logs');
    const btnClear = document.getElementById('btn-clear-terminal-logs');
    const btnAutoScroll = document.getElementById('btn-toggle-autoscroll-logs');
    const term = document.getElementById('terminal-logs-window');

    if (btnCopy && term) {
        btnCopy.addEventListener('click', async () => {
            const text = term.innerText || term.textContent;
            try {
                await navigator.clipboard.writeText(text);
                showToast('📋 Đã sao chép toàn bộ logs vào clipboard!', 'success');
            } catch (err) {
                const textarea = document.createElement('textarea');
                textarea.value = text;
                document.body.appendChild(textarea);
                textarea.select();
                document.execCommand('copy');
                document.body.removeChild(textarea);
                showToast('📋 Đã sao chép logs!', 'success');
            }
        });
    }

    if (btnClear && term) {
        btnClear.addEventListener('click', () => {
            term.innerHTML = '<div class="log-line text-muted">[Console Cleared] Sẵn sàng nhận logs mới...</div>';
            const logsCountEl = document.getElementById('terminal-logs-count');
            if (logsCountEl) logsCountEl.textContent = '1 dòng';
            showToast('🧹 Đã xóa sạch màn hình console!', 'info');
        });
    }

    if (btnAutoScroll) {
        btnAutoScroll.addEventListener('click', () => {
            terminalAutoScroll = !terminalAutoScroll;
            btnAutoScroll.innerHTML = terminalAutoScroll
                ? '<i class="fa-solid fa-arrow-down-short-wide"></i> Auto-Scroll: ON'
                : '<i class="fa-solid fa-pause"></i> Auto-Scroll: OFF';
            if (terminalAutoScroll && term) {
                term.scrollTop = term.scrollHeight;
            }
            showToast(terminalAutoScroll ? 'Đã bật tự động cuộn logs' : 'Đã tạm dừng tự động cuộn logs', 'info');
        });
    }
}
window.initLogsControls = initLogsControls;
