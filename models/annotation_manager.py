from typing import List, Dict, Optional

class AnnotationManager:
    """标注管理器，负责处理标注者身份和会话管理"""
    
    def __init__(self):
        self.current_annotator = None
        self.annotators = [
            "annotator_1",
            "annotator_2", 
            "annotator_3",
            "unassigned"
        ]
    
    def get_all_annotators(self) -> List[str]:
        """获取所有标注者列表"""
        return self.annotators
    
    def get_current_annotator(self) -> Optional[str]:
        """获取当前标注者"""
        return self.current_annotator
    
    def set_current_annotator(self, annotator: str) -> bool:
        """设置当前标注者"""
        if annotator in self.annotators:
            self.current_annotator = annotator
            return True
        return False
    
    def is_annotator_selected(self) -> bool:
        """检查是否已选择标注者"""
        return self.current_annotator is not None
    
    def get_annotator_display_name(self, annotator: str) -> str:
        """获取标注者的显示名称"""
        if annotator == "unassigned":
            return "未分配"
        return f"标注者 {annotator.split('_')[1]}"
