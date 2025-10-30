#!/usr/bin/env python3
"""
管理員審核申訴腳本
用於查看和審核使用者申訴的電影提交
"""
import sys
import os

# 添加專案根目錄到路徑
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.utils.admin_tools import (
    view_appeal_submissions, 
    approve_appeal, 
    reject_appeal,
    print_appeal_details,
    list_all_appeals
)

def main():
    print("="*60)
    print("🎬 電影提交申訴審核系統")
    print("="*60)
    
    while True:
        print("\n📋 選單:")
        print("1. 查看所有待審核申訴")
        print("2. 查看申訴詳情")
        print("3. 批准申訴")
        print("4. 拒絕申訴")
        print("5. 查看申訴統計")
        print("0. 離開")
        
        choice = input("\n請選擇 (0-5): ").strip()
        
        if choice == "0":
            print("👋 再見！")
            break
        elif choice == "1":
            appeals = view_appeal_submissions()
            if appeals:
                print(f"\n⏳ 待審核申訴 ({len(appeals)} 件):")
                for i, appeal in enumerate(appeals, 1):
                    movie_title = appeal.get("movie_data", {}).get("title", "未知電影")
                    print(f"   {i}. [{appeal.get('submission_id')}] {movie_title}")
            else:
                print("✅ 目前沒有待審核的申訴")
        elif choice == "2":
            submission_id = input("請輸入提交ID: ").strip()
            appeals = view_appeal_submissions()
            target = next((a for a in appeals if a.get("submission_id") == submission_id), None)
            if target:
                print_appeal_details(target)
            else:
                print(f"❌ 找不到提交ID: {submission_id}")
        elif choice == "3":
            submission_id = input("請輸入要批准的提交ID: ").strip()
            confirm = input(f"確定要批准 {submission_id} 嗎？(y/N): ").strip().lower()
            if confirm == 'y':
                approve_appeal(submission_id)
            else:
                print("已取消")
        elif choice == "4":
            submission_id = input("請輸入要拒絕的提交ID: ").strip()
            confirm = input(f"確定要拒絕 {submission_id} 嗎？(y/N): ").strip().lower()
            if confirm == 'y':
                reject_appeal(submission_id)
            else:
                print("已取消")
        elif choice == "5":
            list_all_appeals()
        else:
            print("❌ 無效的選項")

if __name__ == "__main__":
    main()

