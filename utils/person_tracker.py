import cv2
import numpy as np

class PersonTracker:
    def __init__(self):
        # 使用 OpenCV 的 HOG 人物检测器
        self.hog = cv2.HOGDescriptor()
        self.hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
        
        # 跟踪器
        self.tracker = None
        self.last_bbox = None
        
    def detect_person(self, frame):
        """检测人物位置"""
        try:
            # 调整图像大小以提高检测速度
            height, width = frame.shape[:2]
            scale = min(1.0, 640 / max(width, height))
            if scale < 1.0:
                new_width = int(width * scale)
                new_height = int(height * scale)
                frame_resized = cv2.resize(frame, (new_width, new_height))
            else:
                frame_resized = frame
                scale = 1.0
            
            # 检测人物
            boxes, weights = self.hog.detectMultiScale(
                frame_resized, 
                winStride=(8, 8),
                padding=(4, 4),
                scale=1.05
            )
            
            if len(boxes) > 0:
                # 选择置信度最高的检测结果
                best_idx = np.argmax(weights)
                x, y, w, h = boxes[best_idx]
                
                # 将坐标转换回原始图像尺寸
                x = int(x / scale)
                y = int(y / scale)
                w = int(w / scale)
                h = int(h / scale)
                
                return (x, y, w, h)
            else:
                return None
                
        except Exception as e:
            print(f"人物检测失败: {e}")
            return None
    
    def initialize_tracker(self, frame, bbox):
        """初始化跟踪器"""
        try:
            # 使用 CSRT 跟踪器（更稳定）
            self.tracker = cv2.TrackerCSRT_create()
            success = self.tracker.init(frame, bbox)
            if success:
                self.last_bbox = bbox
                print("人物跟踪器初始化成功")
            return success
        except Exception as e:
            print(f"跟踪器初始化失败: {e}")
            return False
    
    def track_person(self, frame):
        """跟踪人物位置"""
        try:
            if self.tracker is None:
                return self.last_bbox
            
            success, bbox = self.tracker.update(frame)
            if success:
                self.last_bbox = bbox
                return bbox
            else:
                # 如果跟踪失败，尝试重新检测
                new_bbox = self.detect_person(frame)
                if new_bbox:
                    self.initialize_tracker(frame, new_bbox)
                    return new_bbox
                else:
                    return self.last_bbox
                    
        except Exception as e:
            print(f"人物跟踪失败: {e}")
            # 如果检测失败，使用上一帧的位置
            return self.last_bbox 