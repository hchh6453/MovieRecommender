"""
管理員工具
用於審核使用者提交的電影資訊和申訴
"""
import json
import os
from typing import List, Dict
from datetime import datetime

def view_appeal_submissions(appeal_file: str = "data/user_submissions/appeal_submissions.json") -> List[Dict]:
    """查看所有待審核的申訴"""
    if not os.path.exists(appeal_file):
        print("📋 目前沒有待審核的申訴")
        return []
    
    with open(appeal_file, 'r', encoding='utf-8') as f:
        appeals = json.load(f)
    
    # 只顯示狀態為 "appeal" 的申訴
    pending_appeals = [a for a in appeals if a.get("status") == "appeal"]
    
    return pending_appeals


def approve_appeal(submission_id: str, appeal_file: str = "data/user_submissions/appeal_submissions.json",
                   approved_file: str = "data/user_submissions/approved_submissions.json") -> bool:
    """批准申訴，將電影資訊移到已批准列表"""
    try:
        # 讀取申訴列表
        with open(appeal_file, 'r', encoding='utf-8') as f:
            appeals = json.load(f)
        
        # 找到對應的申訴
        target_appeal = next((a for a in appeals if a.get("submission_id") == submission_id), None)
        if not target_appeal:
            print(f"❌ 找不到提交ID: {submission_id}")
            return False
        
        # 更新狀態
        target_appeal["status"] = "approved"
        target_appeal["reviewed_at"] = datetime.now().isoformat()
        target_appeal["reviewed_by"] = "admin"
        
        # 保存到已批准列表
        if os.path.exists(approved_file):
            with open(approved_file, 'r', encoding='utf-8') as f:
                approved = json.load(f)
        else:
            approved = []
        
        approved.append(target_appeal)
        
        with open(approved_file, 'w', encoding='utf-8') as f:
            json.dump(approved, f, ensure_ascii=False, indent=2)
        
        # 從申訴列表中移除（或標記為已處理）
        appeals = [a for a in appeals if a.get("submission_id") != submission_id]
        with open(appeal_file, 'w', encoding='utf-8') as f:
            json.dump(appeals, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 已批准提交: {submission_id}")
        print(f"   電影名稱: {target_appeal.get('movie_data', {}).get('title', '未知')}")
        return True
        
    except Exception as e:
        print(f"❌ 批准申訴失敗: {e}")
        return False


def reject_appeal(submission_id: str, appeal_file: str = "data/user_submissions/appeal_submissions.json") -> bool:
    """拒絕申訴（維持原拒絕決定）"""
    try:
        # 讀取申訴列表
        with open(appeal_file, 'r', encoding='utf-8') as f:
            appeals = json.load(f)
        
        # 找到對應的申訴
        target_appeal = next((a for a in appeals if a.get("submission_id") == submission_id), None)
        if not target_appeal:
            print(f"❌ 找不到提交ID: {submission_id}")
            return False
        
        # 更新狀態為最終拒絕
        target_appeal["status"] = "finally_rejected"
        target_appeal["reviewed_at"] = datetime.now().isoformat()
        target_appeal["reviewed_by"] = "admin"
        
        # 保存
        with open(appeal_file, 'w', encoding='utf-8') as f:
            json.dump(appeals, f, ensure_ascii=False, indent=2)
        
        print(f"❌ 已拒絕申訴: {submission_id}")
        print(f"   電影名稱: {target_appeal.get('movie_data', {}).get('title', '未知')}")
        return True
        
    except Exception as e:
        print(f"❌ 拒絕申訴失敗: {e}")
        return False


def print_appeal_details(appeal: Dict):
    """列印申訴詳情（供管理員查看）"""
    print("\n" + "="*60)
    print(f"📋 提交ID: {appeal.get('submission_id')}")
    print(f"👤 使用者ID: {appeal.get('user_id')}")
    print(f"📅 提交時間: {appeal.get('timestamp')}")
    print(f"📅 申訴時間: {appeal.get('appeal_timestamp', '未知')}")
    
    movie_data = appeal.get("movie_data", {})
    print(f"\n🎬 電影資訊:")
    print(f"   名稱: {movie_data.get('title', '未知')}")
    print(f"   年份: {movie_data.get('year', '未知')}")
    print(f"   類型: {', '.join(movie_data.get('genres', []))}")
    if movie_data.get('description'):
        print(f"   描述: {movie_data.get('description')[:100]}...")
    
    print(f"\n❓ AI 驗證結果:")
    print(f"   安全性: {'✅ 安全' if appeal.get('validation_safe') else '❌ 不安全'}")
    print(f"   信心度: {appeal.get('validation_confidence', 0):.1%}")
    print(f"   拒絕原因: {appeal.get('validation_reason', '未知')}")
    
    print(f"\n📝 原始訊息:")
    print(f"   {appeal.get('original_message', '')[:200]}...")
    
    print("="*60 + "\n")


def list_all_appeals(appeal_file: str = "data/user_submissions/appeal_submissions.json"):
    """列出所有申訴（包括不同狀態）"""
    if not os.path.exists(appeal_file):
        print("📋 目前沒有申訴記錄")
        return
    
    with open(appeal_file, 'r', encoding='utf-8') as f:
        appeals = json.load(f)
    
    # 分類
    pending = [a for a in appeals if a.get("status") == "appeal"]
    approved = [a for a in appeals if a.get("status") == "approved"]
    rejected = [a for a in appeals if a.get("status") == "finally_rejected"]
    
    print(f"\n📊 申訴統計:")
    print(f"   待審核: {len(pending)} 件")
    print(f"   已批准: {len(approved)} 件")
    print(f"   已拒絕: {len(rejected)} 件")
    
    if pending:
        print(f"\n⏳ 待審核申訴 ({len(pending)} 件):")
        for i, appeal in enumerate(pending, 1):
            movie_title = appeal.get("movie_data", {}).get("title", "未知電影")
            print(f"   {i}. [{appeal.get('submission_id')}] {movie_title}")
            print(f"      使用者: {appeal.get('user_id')}")
            print(f"      拒絕原因: {appeal.get('validation_reason', '未知')[:50]}...")


