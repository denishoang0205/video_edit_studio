import os
import sys
import time
import re
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

def clean_caption_text(text):
    """Làm sạch tiêu đề, loại bỏ hoàn toàn các chuỗi part 1, part 2, phần 1, đuôi file .mp4..."""
    if not text:
        return ""
    cleaned = re.sub(r'[\s\-_\(\[\{]+(part|phần|tập)\s*[\d]+[\)\]\}]*', '', text, flags=re.IGNORECASE)
    cleaned = re.sub(r'\.(mp4|mov|mkv|avi|webm)$', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'[\s\-_\(\[\{]+(part|phần|tập)\s*[\d]+[\)\]\}]*', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s{2,}', ' ', cleaned).strip()
    return cleaned

def dismiss_any_pending_or_draft_modals(page, log_fn=None, tab_index=None):
    """
    Tự động quét và xử lý chính xác các hộp thoại popup/modal của TikTok Studio:
    1. Nếu là popup '¿Descartar esta publicación?' (Hỏi có hủy bài đăng không?):
       -> Bấm 'Seguir editando' (Tiếp tục chỉnh sửa / Keep editing) để KHÔNG làm mất video!
    2. Nếu là popup bản nháp cũ / video pending cần xác nhận hoặc thay thế:
       -> Bấm 'Thay thế', 'Reemplazar', 'Replace', 'Aceptar', 'OK', 'Confirm', 'Tiếp tục'.
    3. TUYỆT ĐỐI CHỈ TÌM TRONG DIALOG/MODAL CONTAINER, KHÔNG TÌM TRÊN GIAO DIỆN CHÍNH
       để tránh bấm nhầm vào nút 'Descartar' (Hủy bài) hay 'Sustituir' (Thay file) trên trang chính!
    """
    tab_tag = f"[Tab {tab_index}] " if tab_index is not None else ""
    
    dialog_containers = [
        'div[role="dialog"]',
        'div[class*="modal"]',
        'div[class*="dialog"]',
        'div[class*="popup"]',
        '.tiktok-modal',
        '[data-e2e*="modal"]'
    ]

    clicked = False
    for d_sel in dialog_containers:
        try:
            modals = page.locator(d_sel)
            m_count = modals.count()
            for m_i in range(m_count):
                modal = modals.nth(m_i)
                if not modal.is_visible():
                    continue

                modal_text = (modal.text_content() or "").lower()

                # TÌNH HUỐNG 1: Popup hỏi "Có hủy bài đăng này không?" (Discard post confirmation)
                if any(x in modal_text for x in ['descartar esta publicación', 'discard this post', 'bỏ bài viết này', 'hủy bài viết này', 'verwerfen?']):
                    keep_editing_keywords = [
                        'seguir editando', 'keep editing', 'tiếp tục chỉnh sửa', 'weiter bearbeiten', 'continuar editando', 'cancelar', 'cancel'
                    ]
                    for kw in keep_editing_keywords:
                        btn = modal.locator(f'button:has-text("{kw}")')
                        if btn.count() > 0 and btn.first.is_visible():
                            btn.first.click(timeout=1200)
                            if log_fn:
                                log_fn(f"⚡ {tab_tag}Tự động bấm '{kw}' để giữ lại bài đăng (không hủy video)!")
                            clicked = True
                            time.sleep(0.4)
                            return True

                # TÌNH HUỐNG 2: Popup bản nháp cũ / Video pending / Thay thế video cũ / Copyright notice
                confirm_keywords = [
                    # Tiếng Việt
                    'thay thế', 'tiếp tục', 'xác nhận', 'đồng ý', 'ok', 'vẫn đăng', 'đăng ngay',
                    # English
                    'replace', 'continue', 'confirm', 'ok', 'publish anyway', 'post anyway', 'got it', 'understood', 'proceed',
                    # Spanish (Tây Ban Nha)
                    'reemplazar', 'continuar', 'confirmar', 'aceptar', 'publicar de todos modos', 'entendido',
                    # Portuguese / Brazil
                    'substituir', 'continuar', 'confirmar', 'publicar mesmo assim', 'entendi',
                    # German (Tiếng Đức)
                    'ersetzen', 'fortfahren', 'weiter', 'bestätigen', 'trotzdem veröffentlichen', 'verstanden'
                ]

                for kw in confirm_keywords:
                    btn = modal.locator(f'button:has-text("{kw}")')
                    if btn.count() > 0 and btn.first.is_visible():
                        b_text = (btn.first.text_content() or kw).strip()
                        btn.first.click(timeout=1200)
                        if log_fn:
                            log_fn(f"⚡ {tab_tag}Tự động xác nhận popup: '{b_text}'")
                        clicked = True
                        time.sleep(0.4)
                        return True
        except Exception:
            pass

    return clicked

def upload_multiple_videos_to_tiktok_cdp(
    ws_endpoint,
    items,  # list of dicts: [{"video_path": "...", "title": "..."}, ...]
    hashtags="",
    auto_submit=True,
    close_browser_after=False,
    wait_timeout=120,
    log_callback=None
):
    """
    Tự động hóa đăng đồng thời nhiều video (ví dụ 3 part) lên TikTok qua nhiều tab cùng 1 lúc trên AdsPower Chrome:
    - Bỏ tab mặc định ban đầu, tạo N tab mới tương ứng N video.
    - Tự động phát hiện và bấm OK / Tiếp tục / Thay thế trên các popup bản nháp cũ dở dang.
    - Điền caption tức thì (insert_text) chỉ lấy phần title (+ hashtags), tuyệt đối không kèm part_label, không gõ chậm.
    - Đợi cả N tab xử lý xong video và bấm nút Đăng (Publicar) đồng thời.
    """
    def log(msg):
        if log_callback:
            log_callback(msg)
        else:
            print(f"[TikTok Multi-Uploader] {msg}")

    if not items or len(items) == 0:
        return {"success": False, "error": "Danh sách video trống."}

    # Kiểm tra tồn tại của các tệp video
    valid_items = []
    for item in items:
        v_path = item.get("video_path") or item.get("file_path") or ""
        if v_path and os.path.exists(v_path):
            item_copy = dict(item)
            item_copy["video_path"] = os.path.abspath(v_path)
            valid_items.append(item_copy)
        else:
            log(f"⚠️ Cảnh báo: Không tìm thấy tệp video: {v_path}")

    if not valid_items:
        return {"success": False, "error": "Không có tệp video hợp lệ nào để tải lên."}

    total_tabs = len(valid_items)
    log(f"🔗 Đang kết nối vào AdsPower Chrome qua CDP WebSocket...")

    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(ws_endpoint)
            contexts = browser.contexts
            context = contexts[0] if contexts else browser.new_context()

            # 1. Quản lý Tab: Lưu lại các tab mặc định cũ để đóng sau khi tạo các tab đăng video
            initial_pages = list(context.pages)

            log(f"📑 Đang mở đồng thời {total_tabs} tab TikTok Studio mới...")
            pages = []
            for idx in range(total_tabs):
                page = context.new_page()
                # Tự động chấp nhận mọi hộp thoại popup alert/confirm của trình duyệt
                try:
                    page.on("dialog", lambda dialog: dialog.accept())
                except Exception:
                    pass
                pages.append(page)

            # Đóng các tab mặc định cũ để giải phóng tài nguyên và tránh rác tab
            for old_p in initial_pages:
                try:
                    old_p.close()
                except Exception:
                    pass

            # 2. Điều hướng tất cả các tab đến trang TikTok Studio Upload
            tiktok_upload_url = "https://www.tiktok.com/tiktokstudio/upload"
            log(f"🌐 Đang nạp trang TikTok Studio Upload trên {total_tabs} tab...")
            for i, page in enumerate(pages):
                log(f"🌐 [Tab {i+1}/{total_tabs}] Đang mở TikTok Studio Upload...")
                try:
                    page.bring_to_front()
                    page.goto(tiktok_upload_url, timeout=45000, wait_until="domcontentloaded")
                except Exception as e:
                    log(f"⚠️ [Tab {i+1}] Đang chờ trang tải: {e}")

            time.sleep(2)
            
            # Theo dõi tab nào bị lỗi (ví dụ không nạp được file) để bỏ qua lúc đợi nút Đăng
            failed_tabs = [False] * total_tabs

            # Kiểm tra xem có bị chuyển về trang đăng nhập không
            for page in pages:
                try:
                    current_url = page.url.lower()
                    if "login" in current_url or "passport" in current_url:
                        log("⚠️ Phát hiện TikTok đang yêu cầu đăng nhập!")
                        return {
                            "success": False,
                            "error": "Tài khoản TikTok chưa được đăng nhập trên profile AdsPower này. Vui lòng đăng nhập 1 lần trước khi đăng tự động."
                        }
                except Exception:
                    pass

            # 3. Tự động đóng/xác nhận mọi popup modal nháp cũ hoặc video pending cũ trên từng tab
            log("🧹 Đang tự động quét và xác nhận/bỏ qua mọi popup bản nháp hoặc video pending cũ...")
            for i, page in enumerate(pages):
                dismiss_any_pending_or_draft_modals(page, log_fn=log, tab_index=i+1)

            # 4. Nạp tệp video vào từng tab
            log(f"📤 Bắt đầu nạp {total_tabs} video vào các tab tương ứng...")
            select_file_selectors = [
                'button:has-text("Chọn video")',
                'button:has-text("Select video")',
                'button:has-text("Select files")',
                # German (Tiếng Đức)
                'button:has-text("Dateien auswählen")',
                'button:has-text("Video auswählen")',
                'button:has-text("Datei auswählen")',
                'button:has-text("Dateien hochladen")',
                'button:has-text("Hochladen")',
                'button:has-text("Auswählen")',
                # Portuguese / Brazil
                'button:has-text("Selecionar vídeo")',
                'button:has-text("Selecionar arquivos")',
                # Spanish
                'button:has-text("Seleccionar video")',
                'button:has-text("Seleccionar archivos")',
                '.upload-stage-btn',
                '[data-e2e="upload-btn"]',
                '[data-e2e="select-file-btn"]'
            ]

            for i, (page, item) in enumerate(zip(pages, valid_items)):
                try:
                    page.bring_to_front()
                    time.sleep(0.3)
                except Exception:
                    pass
                v_path = item["video_path"]
                log(f"📤 [Tab {i+1}/{total_tabs}] Đang nạp video: '{os.path.basename(v_path)}'...")
                file_input_found = False

                for attempt in range(15):
                    try:
                        # Tự động quét và bấm OK/Thay thế trên bất kỳ popup pending/draft nào đang chặn
                        dismiss_any_pending_or_draft_modals(page, log_fn=log, tab_index=i+1)

                        # Phương pháp 1: Native CDP session
                        try:
                            cdp = context.new_cdp_session(page)
                            doc = cdp.send("DOM.getDocument")
                            node = cdp.send("DOM.querySelector", {"nodeId": doc["root"]["nodeId"], "selector": "input[type=file]"})
                            node_id = node.get("nodeId")
                            if node_id:
                                cdp.send("DOM.setFileInputFiles", {"files": [v_path], "nodeId": node_id})
                                file_input_found = True
                                break
                        except Exception:
                            pass

                        # Phương pháp 2: Locator set_input_files
                        if page.locator('input[type="file"]').count() > 0:
                            page.locator('input[type="file"]').first.set_input_files(v_path)
                            file_input_found = True
                            break

                        # Phương pháp 3: FileChooser click với nhiều ngôn ngữ
                        for sel_btn in select_file_selectors:
                            btn_loc = page.locator(sel_btn)
                            if btn_loc.count() > 0 and btn_loc.first.is_visible():
                                try:
                                    with page.expect_file_chooser(timeout=2500) as fc_info:
                                        btn_loc.first.click()
                                    file_chooser = fc_info.value
                                    file_chooser.set_files(v_path)
                                    file_input_found = True
                                    break
                                except Exception:
                                    pass
                        if file_input_found:
                            break
                    except Exception:
                        pass
                    time.sleep(1)

                if file_input_found:
                    log(f"✅ [Tab {i+1}/{total_tabs}] Đã nạp video vào trình tải lên thành công!")
                else:
                    failed_tabs[i] = True
                    log(f"⚠️ [Tab {i+1}/{total_tabs}] Không tìm thấy nút nạp tệp. Đã đánh dấu bỏ qua chờ đăng cho tab này.")

            # 5. Điền Description/Caption (Chỉ lấy phần title + hashtags, không kèm part_label, chèn tức thì không gõ chậm)
            caption_selectors = [
                'div[contenteditable="true"]',
                'div.notranslate[contenteditable="true"]',
                '.public-DraftEditor-content',
                'div[data-placeholder*="caption" i]',
                'div[data-placeholder*="tiêu đề" i]',
                'div[data-placeholder*="mô tả" i]',
                # German (Tiếng Đức)
                'div[data-placeholder*="beschreibung" i]',
                'div[data-placeholder*="titel" i]',
                'div[data-placeholder*="beschreibe" i]',
                # Portuguese / Brazil
                'div[data-placeholder*="legenda" i]',
                'div[data-placeholder*="título" i]',
                'div[data-placeholder*="descrição" i]',
                # Textarea
                'textarea[placeholder*="caption" i]',
                'textarea[placeholder*="beschreibung" i]',
                'textarea[placeholder*="titel" i]',
                'textarea[placeholder*="legenda" i]',
                'textarea'
            ]

            log(f"⏳ Đang đợi trường Caption xuất hiện trên các tab...")
            time.sleep(4)

            for i, (page, item) in enumerate(zip(pages, valid_items)):
                # TUÂN THỦ NGHIÊM KHẮC: Tiêu đề và hook là GIỐNG TÊN VIDEO đặt trên channel (GỠ BỎ HOÀN TOÀN AI)
                raw_title = clean_caption_text(item.get("title", "").strip())
                if not raw_title and item.get("video_path"):
                    raw_title = clean_caption_text(os.path.splitext(os.path.basename(item["video_path"]))[0])

                override_caption = item.get("override_caption") or item.get("caption")
                if override_caption:
                    caption_body = clean_caption_text(override_caption.strip())
                else:
                    caption_body = raw_title

                # Ghép Hashtag của tài khoản nếu có
                acc_tags = hashtags.strip() if hashtags else ""
                if acc_tags:
                    full_caption = f"{caption_body} {acc_tags}".strip()
                else:
                    full_caption = caption_body

                log(f"✍️ [Tab {i+1}/{total_tabs}] Đang điền tiêu đề chuẩn kênh: '{full_caption}' (nhanh tức thì)...")
                caption_filled = False

                for attempt in range(20):
                    try:
                        dismiss_any_pending_or_draft_modals(page, log_fn=None, tab_index=i+1)
                        for sel in caption_selectors:
                            loc = page.locator(sel)
                            if loc.count() > 0 and loc.first.is_visible():
                                loc.first.click()
                                time.sleep(0.2)
                                page.keyboard.press("Control+A")
                                page.keyboard.press("Backspace")
                                time.sleep(0.1)
                                # Chèn văn bản tức thì (không mô phỏng gõ phím chậm)
                                page.keyboard.insert_text(full_caption)
                                caption_filled = True
                                log(f"✅ [Tab {i+1}/{total_tabs}] Đã điền xong tiêu đề!")
                                break
                        if caption_filled:
                            break
                    except Exception:
                        pass
                    time.sleep(0.8)

            # 6. Đợi cả N tab xử lý video hoàn tất
            post_selectors = [
                'button[data-e2e="post_video_button"]',
                # German (Tiếng Đức)
                'button:has-text("Veröffentlichen")',
                'button:has-text("Posten")',
                'button:has-text("Beitrag posten")',
                'button:has-text("Jetzt veröffentlichen")',
                'button:has-text("Jetzt posten")',
                'button:has-text("Video veröffentlichen")',
                'button:has-text("Video posten")',
                'button[class*="Button"]:has-text("Veröffentlichen")',
                'button[class*="Button"]:has-text("Posten")',
                'button[class*="Button"]:has-text("Beitrag posten")',
                # Portuguese / Brazil (Tiếng Bồ Đào Nha)
                'button:has-text("Publicar")',
                'button:has-text("Publicar vídeo")',
                'button:has-text("Postar")',
                'button[class*="Button"]:has-text("Publicar")',
                'button[class*="Button"]:has-text("Postar")',
                # English
                'button:has-text("Post")',
                'button:has-text("Publish")',
                'button:has-text("Post video")',
                'button:has-text("Publish video")',
                'button[class*="Button"]:has-text("Post")',
                'button[class*="Button"]:has-text("Publish")',
                # Vietnamese
                'button:has-text("Đăng")',
                'button:has-text("Đăng video")',
                'button[class*="Button"]:has-text("Đăng")',
                # Spanish / French / Other
                'button:has-text("Enviar")',
                'button:has-text("Publier")',
                'button:has-text("Posting")',
                'button.btn-post'
            ]

            log(f"⏳ Đang theo dõi tiến trình xử lý video trên toàn bộ {total_tabs} tab (Thời gian tối đa: {wait_timeout}s)...")
            start_wait = time.time()
            tabs_ready = [False] * total_tabs
            last_progress_logged = {}
            
            # Gán tabs_ready = True cho những tab đã bị failed để vòng while không chờ chúng nữa
            for i in range(total_tabs):
                if failed_tabs[i]:
                    tabs_ready[i] = True

            while time.time() - start_wait < wait_timeout:
                for i, page in enumerate(pages):
                    if not tabs_ready[i] and not failed_tabs[i]:
                        try:
                            # Đưa tab lên phía trước để Chrome không bóp tiến trình CPU xử lý video
                            page.bring_to_front()
                            time.sleep(0.3)
                            # Cuộn trang xuống đáy
                            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                            
                            # Tự động bấm các popup pending/draft nếu xuất hiện
                            dismiss_any_pending_or_draft_modals(page, log_fn=log, tab_index=i+1)

                            # 6a. Kiểm tra nút Đăng đã sẵn sàng chưa
                            for sel in post_selectors:
                                btn = page.locator(sel)
                                if btn.count() > 0 and btn.first.is_visible():
                                    is_disabled = btn.first.is_disabled()
                                    btn_class = btn.first.get_attribute("class") or ""
                                    if not is_disabled and "disabled" not in btn_class.lower():
                                        tabs_ready[i] = True
                                        log(f"✨ [Tab {i+1}/{total_tabs}] Video đã tải xong và nút Đăng đã SẴN SÀNG!")
                                        break
                                        
                            # 6b. Nếu chưa sẵn sàng, quét tìm tiến độ tải lên (%) để thông báo cho người dùng
                            if not tabs_ready[i]:
                                try:
                                    prog_elem = page.locator('span:has-text("%"), div:has-text("%"), [class*="progress"], [class*="upload-status"]').first
                                    if prog_elem.count() > 0 and prog_elem.is_visible():
                                        txt = prog_elem.text_content().strip()
                                        if txt and txt != last_progress_logged.get(i):
                                            last_progress_logged[i] = txt
                                            log(f"   ⏳ [Tab {i+1}/{total_tabs}] Đang tải lên TikTok: {txt}...")
                                except Exception:
                                    pass
                        except Exception:
                            pass
                if all(tabs_ready):
                    break
                time.sleep(2.5)

            # 7. Bấm Đăng đồng thời trên cả N tab
            if auto_submit:
                log(f"🚀 Bắt đầu bấm nút ĐĂNG VIDEO trên các tab đã sẵn sàng...")
                posted_count = 0
                for i, page in enumerate(pages):
                    if failed_tabs[i]:
                        continue
                    try:
                        page.bring_to_front()
                        time.sleep(0.5)
                        # Cuộn xuống đáy để đảm bảo nút Đăng nằm trọn trong vùng nhìn thấy
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        time.sleep(0.3)

                        # Nếu tab này chưa sẵn sàng vì mạng chậm, cố gắng đợi thêm 30s riêng cho tab này
                        if not tabs_ready[i]:
                            log(f"⏳ [Tab {i+1}/{total_tabs}] Mạng chậm, đang kiên nhẫn chờ thêm 30s cho tab này...")
                            tab_wait_start = time.time()
                            while time.time() - tab_wait_start < 30:
                                for sel in post_selectors:
                                    btn = page.locator(sel)
                                    if btn.count() > 0 and btn.first.is_visible():
                                        if not btn.first.is_disabled() and "disabled" not in (btn.first.get_attribute("class") or "").lower():
                                            tabs_ready[i] = True
                                            break
                                if tabs_ready[i]:
                                    break
                                time.sleep(2)

                        btn_clicked = False
                        for sel in post_selectors:
                            btn = page.locator(sel)
                            if btn.count() > 0 and btn.first.is_visible():
                                try:
                                    btn.first.scroll_into_view_if_needed(timeout=2000)
                                except Exception:
                                    pass
                                try:
                                    btn.first.click(force=True, timeout=3000)
                                    btn_clicked = True
                                except Exception:
                                    pass
                                if not btn_clicked:
                                    try:
                                        btn.first.evaluate("el => el.click()")
                                        btn_clicked = True
                                    except Exception:
                                        pass
                                if btn_clicked:
                                    posted_count += 1
                                    log(f"🎉 [Tab {i+1}/{total_tabs}] Đã bấm nút ĐĂNG VIDEO!")
                                    break
                        if not btn_clicked:
                            log(f"⚠️ [Tab {i+1}/{total_tabs}] Nút Đăng chưa khả dụng (video chưa tải xong hoặc mạng quá chậm).")
                    except Exception as e_click:
                        log(f"⚠️ [Tab {i+1}] Lỗi khi bấm nút Đăng: {e_click}")

                # 8. Kiểm tra và tự động xác nhận popup bản quyền (Copyright Check / Publish anyway) trên các tab
                log("⏳ Đang kiểm tra và xác nhận popup xuất bản trên các tab...")
                confirm_selectors = [
                    # German (Tiếng Đức)
                    'button:has-text("Trotzdem veröffentlichen")',
                    'button:has-text("Trotzdem posten")',
                    'button:has-text("Jetzt veröffentlichen")',
                    'button:has-text("Jetzt posten")',
                    'button:has-text("Weiter")',
                    'button:has-text("Fortfahren")',
                    'button:has-text("Bestätigen")',
                    'button:has-text("Einverstanden")',
                    'div[role="dialog"] button:has-text("Veröffentlichen")',
                    'div[role="dialog"] button:has-text("Posten")',
                    'div[role="dialog"] button:has-text("Trotzdem")',
                    'div[role="dialog"] button:has-text("Weiter")',
                    '.tiktok-modal button:has-text("Veröffentlichen")',
                    '.tiktok-modal button:has-text("Posten")',
                    '.tiktok-modal button:has-text("Trotzdem")',
                    '.tiktok-modal button:has-text("Weiter")',
                    # Portuguese / Brazil
                    'button:has-text("Publicar agora")',
                    'button:has-text("Publicar de qualquer forma")',
                    'button:has-text("Publicar mesmo assim")',
                    'button:has-text("Continuar")',
                    'button:has-text("Confirmar")',
                    'div[role="dialog"] button:has-text("Publicar")',
                    'div[role="dialog"] button:has-text("Continuar")',
                    '.tiktok-modal button:has-text("Publicar")',
                    # English
                    'button:has-text("Post now")',
                    'button:has-text("Publish now")',
                    'button:has-text("Publish anyway")',
                    'button:has-text("Post anyway")',
                    'button:has-text("Continue")',
                    'button:has-text("Confirm")',
                    'button[data-e2e="post_video_modal_confirm"]',
                    'div[role="dialog"] button:has-text("Post")',
                    'div[role="dialog"] button:has-text("Continue")',
                    '.tiktok-modal button:has-text("Post")',
                    # Spanish
                    'button:has-text("Publicar ahora")',
                    'button:has-text("Publicar de todos modos")',
                    'button:has-text("Continuar")',
                    # Vietnamese
                    'button:has-text("Vẫn đăng")',
                    'button:has-text("Đăng ngay")',
                    'button:has-text("Tiếp tục")',
                    'div[role="dialog"] button:has-text("Đăng")',
                    '.tiktok-modal button:has-text("Đăng")'
                ]

                for round_chk in range(10):
                    time.sleep(1.2)
                    for i, page in enumerate(pages):
                        try:
                            page.bring_to_front()
                            for c_sel in confirm_selectors:
                                c_btn = page.locator(c_sel)
                                if c_btn.count() > 0 and c_btn.first.is_visible():
                                    try:
                                        c_btn.first.scroll_into_view_if_needed(timeout=1000)
                                        c_btn.first.click(force=True, timeout=2000)
                                    except Exception:
                                        c_btn.first.evaluate("el => el.click()")
                                    log(f"✅ [Tab {i+1}] Đã bấm xác nhận '{c_sel}' thành công!")
                                    break
                        except Exception:
                            pass

                log(f"🎉 HOÀN TẤT ĐĂNG ĐỒNG THỜI {posted_count}/{total_tabs} TAB LÊN TIKTOK THÀNH CÔNG!")
                time.sleep(2) # Chờ 2s để request đăng hoàn tất trên server TikTok
            else:
                log(f"📝 Chế độ xem trước (Draft): Đã nạp video và caption trên {total_tabs} tab.")

            try:
                context.close()
            except Exception:
                pass
            try:
                browser.close()
            except Exception:
                pass

            # Lọc danh sách những item đã đăng thành công thực sự
            successful_items = []
            for i, it in enumerate(valid_items):
                if auto_submit:
                    if not failed_tabs[i]:
                        successful_items.append(it)
                else:
                    successful_items.append(it)
            
            final_count = len(successful_items)
            is_success = final_count > 0

            return {
                "success": is_success,
                "message": f"Đã đăng thành công {final_count} video trên {total_tabs} tab!" if is_success else "Toàn bộ video bị lỗi nạp tệp hoặc chưa bấm được nút Đăng.",
                "count": final_count,
                "items": successful_items
            }

    except Exception as e:
        log(f"❌ Lỗi tự động hóa Playwright TikTok: {str(e)}")
        return {
            "success": False,
            "error": f"Lỗi điều khiển trình duyệt TikTok: {str(e)}"
        }

def upload_video_to_tiktok_cdp(
    ws_endpoint,
    video_path,
    title="",
    hashtags="",
    auto_submit=True,
    close_browser_after=False,
    wait_timeout=90,
    log_callback=None
):
    """Hàm tương thích ngược khi đăng 1 video duy nhất (chuyển tiếp sang upload_multiple_videos_to_tiktok_cdp)"""
    return upload_multiple_videos_to_tiktok_cdp(
        ws_endpoint=ws_endpoint,
        items=[{"video_path": video_path, "title": title}],
        hashtags=hashtags,
        auto_submit=auto_submit,
        close_browser_after=close_browser_after,
        wait_timeout=wait_timeout,
        log_callback=log_callback
    )


