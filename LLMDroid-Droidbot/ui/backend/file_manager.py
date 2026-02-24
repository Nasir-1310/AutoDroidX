"""
File Manager - Read output files and coverage data
"""
import os
import re
from typing import Dict, Any, List, Optional
from datetime import datetime


class FileManager:
    def __init__(self):
        self._coverage_pattern = re.compile(
            r'\[([^\]]+)\]\s+(\d+\.\d+)%\s+\((\d+)/(\d+)\)\s+-->\s+(\d+\.\d+)'
        )
    
    def list_files(self, output_dir: str) -> Dict[str, Any]:
        """List files in output directory"""
        if not os.path.exists(output_dir):
            return {"files": [], "error": "Directory not found"}
        
        files = []
        try:
            for item in os.listdir(output_dir):
                item_path = os.path.join(output_dir, item)
                is_dir = os.path.isdir(item_path)
                
                file_info = {
                    "name": item,
                    "path": item_path,
                    "is_directory": is_dir,
                    "size": os.path.getsize(item_path) if not is_dir else None,
                    "modified": datetime.fromtimestamp(
                        os.path.getmtime(item_path)
                    ).isoformat()
                }
                
                # Add icon based on type
                if is_dir:
                    file_info["icon"] = "folder"
                elif item.endswith(('.png', '.jpg', '.jpeg')):
                    file_info["icon"] = "image"
                elif item.endswith('.json'):
                    file_info["icon"] = "json"
                elif item.endswith('.txt'):
                    file_info["icon"] = "text"
                elif item.endswith('.log'):
                    file_info["icon"] = "log"
                else:
                    file_info["icon"] = "file"
                
                files.append(file_info)
            
            # Sort: directories first, then by name
            files.sort(key=lambda x: (not x["is_directory"], x["name"].lower()))
            
        except Exception as e:
            return {"files": [], "error": str(e)}
        
        return {"files": files}
    
    def get_file_content(self, output_dir: str, filename: str) -> Dict[str, Any]:
        """Get content of a file"""
        file_path = os.path.join(output_dir, filename)
        
        if not os.path.exists(file_path):
            return {"error": "File not found"}
        
        if os.path.isdir(file_path):
            return self.list_files(file_path)
        
        # Check file size
        file_size = os.path.getsize(file_path)
        if file_size > 5 * 1024 * 1024:  # 5MB limit
            return {
                "error": "File too large",
                "size": file_size,
                "truncated": True
            }
        
        try:
            # Handle images
            if filename.endswith(('.png', '.jpg', '.jpeg')):
                import base64
                with open(file_path, 'rb') as f:
                    encoded = base64.b64encode(f.read()).decode('utf-8')
                return {
                    "type": "image",
                    "content": encoded,
                    "mime": "image/png" if filename.endswith('.png') else "image/jpeg"
                }
            
            # Handle text files
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            
            return {
                "type": "text",
                "content": content,
                "size": file_size
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    def get_coverage_data(self, output_dir: str) -> Dict[str, Any]:
        """Parse coverage data from codecoverage.txt"""
        coverage_file = os.path.join(output_dir, "codecoverage.txt")
        
        if not os.path.exists(coverage_file):
            # Don't spam log for missing file - it's normal at startup
            return {
                "percentage": 0,
                "covered": 0,
                "total": 0,
                "history": [],
                "growth_rates": [],
                "file_exists": False
            }
        
        try:
            history = []
            growth_rates = []
            percentage = 0
            covered = 0
            total = 0
            
            with open(coverage_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
                for line in lines:
                    match = self._coverage_pattern.search(line)
                    if match:
                        tag = match.group(1)
                        pct = float(match.group(2))
                        cov = int(match.group(3))
                        tot = int(match.group(4))
                        rate = float(match.group(5))
                        
                        percentage = pct
                        covered = cov
                        total = tot
                        
                        history.append({
                            "percentage": pct,
                            "covered": cov,
                            "total": tot,
                            "growth_rate": rate
                        })
                        growth_rates.append(rate)
            
            return {
                "percentage": percentage,
                "covered": covered,
                "total": total,
                "history": history[-100:],  # Last 100 entries
                "growth_rates": growth_rates[-100:],
                "is_stuck": len(growth_rates) >= 5 and all(r == 0 for r in growth_rates[-5:]),
                "file_exists": True
            }
            
        except Exception as e:
            print(f"[FileManager] Error parsing coverage file: {e}")
            return {
                "percentage": 0,
                "covered": 0,
                "total": 0,
                "history": [],
                "error": str(e),
                "file_exists": True
            }
    
    def get_screenshots(self, output_dir: str) -> List[Dict[str, str]]:
        """Get list of screenshots"""
        screenshots_dir = os.path.join(output_dir, "states")
        if not os.path.exists(screenshots_dir):
            return []
        
        screenshots = []
        try:
            for item in os.listdir(screenshots_dir):
                if item.endswith(('.png', '.jpg')):
                    screenshots.append({
                        "name": item,
                        "path": os.path.join(screenshots_dir, item)
                    })
            screenshots.sort(key=lambda x: x["name"], reverse=True)
        except Exception:
            pass
        
        return screenshots[:20]  # Last 20 screenshots
