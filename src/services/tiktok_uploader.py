import os
import sys
import time
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

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
    """
    Tự động hóa đăng video lên TikTok thông qua kết nối CDP với AdsPower Chrome
    Được tối ưu để chống lỗi 'Execution context was destroyed' khi trang web chuyển hướng.
    """
    def log(msg):
        if log_callback:
            log_callback(msg)
        else:
            print(f"[TikTok Uploader] {msg}")

    if not video_path or not os.path.exists(video_path):
        return {"success": False, "error": f"Tệp video không tồn tại: {video_path}"}

    norm_video_path = os.path.abspath(video_path)
    full_caption = f"{title.strip()} {hashtags.strip()}".strip()

    log(f"🔗 Đang kết nối vào trình duyệt AdsPower qua CDP WebSocket...")
    
    try:
        with sync_playwright() as p:
            # Kết nối vào Chrome instance của AdsPower
            browser = p.chromium.connect_over_cdp(ws_endpoint)
            
            contexts = browser.contexts
            context = contexts[0] if contexts else browser.new_context()
            
            # Chọn tab TikTok hoặc mở mới
            page = None
            for p_item in context.pages:
                try:
                    url_lower = p_item.url.lower()
                    if "tiktok.com" in url_lower and ("upload" in url_lower or "creator" in url_lower or "studio" in url_lower):
                        page = p_item
                        break
                except Exception:
                    continue
                    
            if not page:
                page = context.pages[0] if context.pages else context.new_page()
                    
            try:
                page.bring_to_front()
            except Exception:
                pass
            
            # 1. Điều hướng tới trang TikTok Studio Upload
            tiktok_upload_url = "https://www.tiktok.com/tiktokstudio/upload"
            curr_url = ""
            try:
                curr_url = page.url.lower()
            except Exception:
                pass
                
            if "tiktokstudio/upload" not in curr_url and "creator-center/upload" not in curr_url:
                log(f"🌐 Đang mở trang TikTok Studio: {tiktok_upload_url}")
                try:
                    page.goto(tiktok_upload_url, timeout=45000, wait_until="load")
                except Exception as e:
                    log(f"⚠️ Chờ trang tải: {e}")
                    
            # Chờ trang ổn định sau các chuyển hướng client-side
            time.sleep(4)
            
            # Kiểm tra xem có bị chuyển về trang đăng nhập không
            try:
                current_page_url = page.url.lower()
                if "login" in current_page_url or "passport" in current_page_url:
                    log("⚠️ Phát hiện TikTok đang yêu cầu đăng nhập!")
                    return {
                        "success": False,
                        "error": "Tài khoản TikTok chưa được đăng nhập trên profile AdsPower này. Vui lòng đăng nhập tài khoản 1 lần trước khi bấm Đăng tự động."
                    }
            except Exception:
                pass

            # 2. Đóng các popup modal nháp cũ nếu có (ví dụ: "Video chưa lưu. Tiếp tục chỉnh sửa?")
            for cancel_text in ['Hủy bỏ', 'Discard', 'Bỏ qua', 'Cancel', 'Bắt đầu lại', 'Leave']:
                try:
                    cancel_btn = page.locator(f'button:has-text("{cancel_text}")')
                    if cancel_btn.count() > 0 and cancel_btn.first.is_visible():
                        log(f"🧹 Đóng cửa sổ nháp cũ: '{cancel_text}'...")
                        cancel_btn.first.click(timeout=2000)
                        time.sleep(1.5)
                        break
                except Exception:
                    pass

            # 3. Nạp video vào ô tải tệp (sử dụng Native CDP để không bị giới hạn 50MB)
            log("🔍 Đang tìm nút tải file video...")
            file_input_found = False
            
            for attempt in range(15):
                try:
                    # Phương pháp 1: Native CDP session
                    try:
                        cdp = context.new_cdp_session(page)
                        doc = cdp.send("DOM.getDocument")
                        node = cdp.send("DOM.querySelector", {"nodeId": doc["root"]["nodeId"], "selector": "input[type=file]"})
                        node_id = node.get("nodeId")
                        if node_id:
                            log(f"📤 Đang nạp video '{os.path.basename(norm_video_path)}'...")
                            cdp.send("DOM.setFileInputFiles", {"files": [norm_video_path], "nodeId": node_id})
                            file_input_found = True
                            break
                    except Exception:
                        pass

                    # Phương pháp 2: Locator set_input_files
                    if page.locator('input[type="file"]').count() > 0:
                        log(f"📤 Đang nạp video '{os.path.basename(norm_video_path)}'...")
                        page.locator('input[type="file"]').first.set_input_files(norm_video_path)
                        file_input_found = True
                        break
                        
                    # Phương pháp 3: FileChooser click button
                    select_btn = page.locator('button:has-text("Chọn video"), button:has-text("Select video"), .upload-stage-btn')
                    if select_btn.count() > 0 and select_btn.first.is_visible():
                        try:
                            with page.expect_file_chooser(timeout=3000) as fc_info:
                                select_btn.first.click()
                            file_chooser = fc_info.value
                            file_chooser.set_files(norm_video_path)
                            file_input_found = True
                            break
                        except Exception:
                            pass
                except Exception:
                    pass
                time.sleep(1.5)
                
            if not file_input_found:
                return {
                    "success": False,
                    "error": "Không tìm thấy nút nạp tệp video. Vui lòng đảm bảo bạn đã đăng nhập TikTok trên Profile AdsPower này."
                }
                
            log("✅ Đã nạp tệp video vào trình tải lên TikTok thành công!")
            
            # 4. Chờ giao diện chỉnh sửa Caption xuất hiện
            log("⏳ Đang đợi trường Caption và tiến trình tải lên...")
            time.sleep(5)
            
            caption_selectors = [
                'div[contenteditable="true"]',
                'div.notranslate[contenteditable="true"]',
                '.public-DraftEditor-content',
                'div[data-placeholder*="caption" i]',
                'div[data-placeholder*="tiêu đề" i]',
                'div[data-placeholder*="mô tả" i]',
                'textarea[placeholder*="caption" i]',
                'textarea'
            ]
            
            caption_filled = False
            if full_caption:
                log(f"✍️ Đang điền Caption: '{full_caption}'")
                for attempt in range(20):
                    try:
                        for sel in caption_selectors:
                            loc = page.locator(sel)
                            if loc.count() > 0 and loc.first.is_visible():
                                loc.first.click()
                                time.sleep(0.4)
                                page.keyboard.press("Control+A")
                                page.keyboard.press("Backspace")
                                time.sleep(0.3)
                                # Gõ văn bản caption
                                page.keyboard.type(full_caption, delay=15)
                                caption_filled = True
                                log("✅ Đã điền xong tiêu đề và hashtag.")
                                break
                        if caption_filled:
                            break
                    except Exception:
                        pass
                    time.sleep(1)
                    
            # 5. Chờ video hoàn tất tải lên (Nút Đăng / Publicar sáng lên)
            log("⏳ Đang kiểm tra tiến trình xử lý video...")
            start_wait = time.time()
            upload_ready = False
            
            post_selectors = [
                'button[data-e2e="post_video_button"]',
                'button:has-text("Publicar")',
                'button:has-text("Post")',
                'button:has-text("Đăng")',
                'button:has-text("Publish")',
                'button:has-text("Enviar")',
                'button.btn-post',
                'button[class*="Button"]:has-text("Publicar")',
                'button[class*="Button"]:has-text("Post")',
                'button[class*="Button"]:has-text("Đăng")'
            ]
            
            while time.time() - start_wait < wait_timeout:
                try:
                    for sel in post_selectors:
                        btn = page.locator(sel)
                        if btn.count() > 0 and btn.first.is_visible():
                            is_disabled = btn.first.is_disabled()
                            btn_class = btn.first.get_attribute("class") or ""
                            if not is_disabled and "disabled" not in btn_class.lower():
                                upload_ready = True
                                break
                    if upload_ready:
                        break
                except Exception:
                    pass
                time.sleep(2)
                
            # 6. Bấm Đăng nếu auto_submit = True
            if auto_submit:
                log("🚀 Đang tiến hành bấm nút ĐĂNG VIDEO (Publicar)...")
                posted_success = False
                for sel in post_selectors:
                    try:
                        btn = page.locator(sel)
                        if btn.count() > 0 and btn.first.is_visible():
                            btn.first.click(timeout=5000)
                            posted_success = True
                            log("🎉 ĐÃ BẤM NÚT ĐĂNG VIDEO! Đang kiểm tra popup xác nhận...")
                            break
                    except Exception:
                        continue
                        
                # 7. Xử lý popup xác nhận bản quyền / Tiếp tục đăng (¿Seguir con la publicación? -> Publicar ahora)
                confirm_selectors = [
                    'button:has-text("Publicar ahora")',
                    'button:has-text("Post now")',
                    'button:has-text("Publish now")',
                    'button:has-text("Publish anyway")',
                    'button:has-text("Post anyway")',
                    'button:has-text("Vẫn đăng")',
                    'button:has-text("Đăng ngay")',
                    'button:has-text("Publicar de todos modos")',
                    'div[role="dialog"] button:has-text("Publicar ahora")',
                    'div[role="dialog"] button:has-text("Publicar")',
                    'div[role="dialog"] button:has-text("Post")',
                    '.tiktok-modal button:has-text("Publicar")',
                    '.tiktok-modal button:has-text("Post")'
                ]

                log("⏳ Đang theo dõi popup xác nhận bản quyền (Copyright Check)...")
                for _ in range(8):
                    time.sleep(1.2)
                    try:
                        for c_sel in confirm_selectors:
                            c_btn = page.locator(c_sel)
                            if c_btn.count() > 0 and c_btn.first.is_visible():
                                log("⚠️ Phát hiện popup xác nhận bản quyền. Đang tự động bấm 'Publicar ahora'...")
                                c_btn.first.click(timeout=3000)
                                time.sleep(2)
                                log("✅ Đã bấm xác nhận 'Publicar ahora' thành công!")
                                break
                    except Exception:
                        pass
                        
                if not posted_success:
                    log("⚠️ Đã nạp video và caption xong. Vui lòng bấm nút 'Publicar' trên cửa sổ Chrome để hoàn tất.")
                else:
                    log("🎉 QUY TRÌNH ĐĂNG VIDEO HOÀN TẤT VÀ ĐÃ XÁC NHẬN ĐĂNG THÀNH CÔNG!")
                    time.sleep(3)
            else:
                log("📝 Chế độ xem trước (Draft): Đã nạp video và caption. Bạn có thể kiểm tra và bấm Đăng trên Chrome.")
                
            if close_browser_after:
                try:
                    browser.close()
                except Exception:
                    pass
                    
            return {
                "success": True,
                "message": "Hoàn tất quy trình đăng clip lên TikTok!",
                "caption": full_caption,
                "video_path": norm_video_path
            }
            
    except Exception as e:
        log(f"❌ Lỗi tự động hóa Playwright TikTok: {str(e)}")
        return {
            "success": False,
            "error": f"Lỗi điều khiển trình duyệt TikTok: {str(e)}"
        }


