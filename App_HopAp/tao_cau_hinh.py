#!/usr/bin/env python3
"""Tạo public/firebase-config.js từ firebase_bi_mat.json, CHỈ lấy các trường công khai của app web.

Mật khẩu/email/UID của Pi không bao giờ được chép vào app. Chạy lại khi đổi project Firebase:
    python tao_cau_hinh.py
"""
import json
from pathlib import Path

PUBLIC_KEYS = ('apiKey', 'authDomain', 'databaseURL', 'projectId', 'appId')
here = Path(__file__).resolve().parent
secret = json.loads((here.parent / 'firebase_bi_mat.json').read_text(encoding='utf-8-sig'))
config = {key: secret[key] for key in PUBLIC_KEYS}
assert not {'pi_password', 'pi_email', 'pi_uid'} & set(config)
(here / 'public' / 'firebase-config.js').write_text(
    '// Tạo bởi tao_cau_hinh.py. Các giá trị này là cấu hình công khai của app web Firebase;\n'
    '// quyền truy cập dữ liệu do database.rules.json quyết định.\n'
    f'export const firebaseConfig = {json.dumps(config, indent=2)};\n', encoding='utf-8')
(here / '.firebaserc').write_text(json.dumps({'projects': {'default': config['projectId']}}, indent=2) + '\n',
                                  encoding='utf-8')
print('Đã tạo public/firebase-config.js và .firebaserc cho project', config['projectId'])
