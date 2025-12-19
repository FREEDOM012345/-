import time

import cv2

from selenium.webdriver.common.action_chains import ActionChains

class SliderVB:
    def __init__(self, driver, bg_element, slider_element):
        self.driver = driver
        self.bg_element = bg_element
        self.slider_element = slider_element

    # 保存滑块背景和滑块图片
    def get_captcha_images(self):
        """
        获取验证码背景图和滑块图
        return: 背景图路径, 滑块图路径
        """

        # 保存背景图
        self.bg_element.screenshot("background.png")

        # 保存滑块图
        self.slider_element.screenshot("slider.png")

        return "background.png", "slider.png"

    # 计算滑块需移动距离
    def calculate_distance(self, background_path, slider_path, min_x=60):
        """
        计算滑块需要移动的距离
        :param: min_x: 忽略左侧多少像素的区域（防止匹配到滑块本身）
        :return: 缺口位置    
        """
        # 读取图片
        background = cv2.imread(background_path)
        slider = cv2.imread(slider_path)

        # 转换为灰度图
        background_gray = cv2.cvtColor(background, cv2.COLOR_BGR2GRAY)
        slider_gray = cv2.cvtColor(slider, cv2.COLOR_BGR2GRAY)
        
        # 如果背景图中包含滑块（有些验证码是这样的），需要把左侧滑块区域遮盖或忽略
        # 这里我们简单地只在 min_x 之后的区域搜索
        # 裁剪背景图
        background_gray_cropped = background_gray[:, min_x:]

        # 边缘检测
        background_edges = cv2.Canny(background_gray_cropped, 50, 150)
        slider_edges = cv2.Canny(slider_gray, 50, 150)

        # 模板匹配
        result = cv2.matchTemplate(background_edges, slider_edges, cv2.TM_CCOEFF_NORMED)

        # 获取最佳匹配位置
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
        
        # max_loc[0] 是在裁剪后的图像中的 x 坐标，需要加上 min_x
        final_x = max_loc[0] + min_x

        # 返回缺口位置（x坐标）
        return final_x

    # 生成人类轨迹
    def get_track(self,distance):
        """
        根据移动距离获取轨迹
        :param: distance: 移动距离
        :return: 移动轨迹
        """
        track = []
        current = 0
        mid = distance * 4 / 5
        t = 0.2
        v = 0

        while current < distance:
            if current < mid:
                a = 2
            else:
                a = -3
            v0 = v
            v = v0 + a * t
            move = v0 * t + 1 / 2 * a * t * t
            current += move
            track.append(round(move))

        # 修正最后误差
        # 如果跑过头了或者没跑够，简单修正一下（通常最后一段很小）
        # 这里简化处理，直接返回
        return track

    # 移动滑块
    def drag_slider(self, distance):
        """
        拖动滑块到指定位置
        :param: distance 移动距离
        :return: None
        """
        actions = ActionChains(self.driver)
        actions.click_and_hold(self.slider_element).perform()
        time.sleep(0.2)
        
        track = self.get_track(distance)
        
        for x in track:
            actions.move_by_offset(xoffset=x, yoffset=0).perform()
            # 随机微小延时
            # time.sleep(uniform(0.01, 0.03)) 
            # ActionChains内部执行太快，有时候需要一点点sleep，但不能太慢
        
        # 模拟人手抖动（可选）
        # actions.move_by_offset(xoffset=-3, yoffset=0).perform()
        # actions.move_by_offset(xoffset=3, yoffset=0).perform()
        
        time.sleep(0.5)
        actions.release().perform()
        
        # 等待验证完成
        time.sleep(1.5)


    # 启动入口
    def slider_ver(self):
        """
        启动滑块验证破解
        :return: None
        """
        try:
            # 获取验证码图片及元素对象
            bg_path, slider_path = self.get_captcha_images()

            # 1. 计算图片缺口位置 (Image Pixels)
            # min_x 设置为 60，假设滑块初始位置在左边且宽度不超过60px，避免匹配到初始滑块
            image_distance = self.calculate_distance(bg_path, slider_path, min_x=60)
            print(f"识别到的缺口位置(图片坐标): {image_distance}px")
            
            # 2. 计算缩放比例
            # 读取保存的图片获取实际分辨率
            real_bg = cv2.imread(bg_path)
            real_width = real_bg.shape[1]
            
            # 获取网页上显示的宽度
            rendered_width = self.bg_element.size['width']
            
            scale = rendered_width / real_width
            print(f"图片缩放比例: {scale:.2f} (网页宽度: {rendered_width}, 图片实际宽度: {real_width})")
            
            # 3. 计算实际需要移动的屏幕距离
            # 目标位置（相对于背景图左边缘）
            target_offset = image_distance * scale
            
            # 滑块当前位置（相对于背景图左边缘）
            # 通常滑块初始位置就在背景图的最左侧或者有固定的微小偏移
            # 我们可以通过计算元素位置差来获取
            bg_x = self.bg_element.location['x']
            slider_x = self.slider_element.location['x']
            initial_offset = slider_x - bg_x
            
            # 如果 initial_offset 是负数或者很大，说明定位可能有误，或者不在同一个坐标系
            # 此时通常假设滑块是从 0 或者一个固定边距开始
            # 这里为了保险，如果 initial_offset 看起来合理（比如 0-50px），就用它，否则假设为 0
            if initial_offset < 0 or initial_offset > 100:
                print(f"警告: 初始偏移量异常 ({initial_offset})，重置为0")
                initial_offset = 0
                
            final_distance = target_offset - initial_offset
            
            # 某些验证码可能有固定的边框偏差，如果总是偏左或偏右，可以在这里微调
            # final_distance -= 5  # 例如：减去滑块自身的透明边距
            
            print(f"计算出的移动距离: {final_distance}px")

            # 拖动滑块
            self.drag_slider(final_distance)

            # 等待验证完成
            time.sleep(2)
            print("滑动操作完成")

        except Exception as e:
            print('出错啦!',e)
            import traceback
            traceback.print_exc()  

