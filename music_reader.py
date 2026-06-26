import fitz  # PyMuPDF
import tkinter as tk
from PIL import Image, ImageTk
import threading
import time
import sys

class CachedDualScreenReader:
    def __init__(self, root, pdf_path):
        self.root = root
        self.root.title("DIY GVIDO Prototype (Threaded Caching)")
        
        # Load the PDF document
        try:
            self.doc = fitz.open(pdf_path)
            self.total_pages = len(self.doc)
        except Exception as e:
            print(f"Error loading PDF: {e}")
            sys.exit(1)
            
        self.current_left_page = 0
        
        # This dictionary will store our pre-rendered PhotoImage objects
        # Key: page_number (int) -> Value: ImageTk.PhotoImage
        self.page_cache = {}
        
        # UI Setup
        self.left_label = tk.Label(root, bg="black", fg="white", font=("Arial", 24))
        self.left_label.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)
        
        self.right_label = tk.Label(root, bg="black", fg="white", font=("Arial", 24))
        self.right_label.pack(side=tk.RIGHT, expand=True, fill=tk.BOTH)
        
        # Show a loading state initially
        self.left_label.config(text="Loading score...")
        self.right_label.config(text="Please wait...")

        # Bind controls
        self.root.bind("<Right>", lambda e: self.next_pages())
        self.root.bind("<Left>", lambda e: self.prev_pages())
        self.root.bind("<space>", lambda e: self.next_pages())
        
        # 🚀 START THE CACHE WORKER THREAD
        # This keeps the UI responsive while processing the PDF in the background
        self.cache_thread = threading.Thread(target=self.pre_render_all_pages, daemon=True)
        self.cache_thread.start()

        # Check periodically if the first couple of pages are ready to display
        self.check_initial_load()

    def pre_render_all_pages(self):
        """Worker thread function that caches pages as bitmaps in the background."""
        print("Background cache thread started...")
        zoom = 1.5  # Boost resolution for crisp sheet music
        mat = fitz.Matrix(zoom, zoom)

        for page_num in range(self.total_pages):
            page = self.doc[page_num]
            pix = page.get_pixmap(matrix=mat)
            
            # Convert to PIL Image
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            
            # Store raw PIL image in cache first (Tkinter objects must be created on main thread)
            self.page_cache[page_num] = img
            print(f"Cached page {page_num + 1}/{self.total_pages}")
            
            # Small sleep to prevent hammering the CPU if it's a massive file
            time.sleep(0.01)
            
        print("All pages successfully cached in memory!")

    def check_initial_load(self):
        """Waits until pages 0 and 1 are cached, then displays them."""
        if 0 in self.page_cache and (1 in self.page_cache or self.total_pages == 1):
            self.update_displays()
        else:
            # Re-check in 100ms if pages aren't ready yet
            self.root.after(100, self.check_initial_load)

    def get_tkinter_image(self, page_num):
        """Retrieves the pre-rendered image from cache and converts it for Tkinter."""
        if page_num < 0 or page_num >= self.total_pages:
            return None
            
        # Pull the raw PIL image from our background cache
        pil_img = self.page_cache.get(page_num)
        if pil_img:
            return ImageTk.PhotoImage(pil_img)
        return None

    def update_displays(self):
        """Updates both screens near-instantaneously using cached items."""
        start_time = time.time()

        # Render Left
        self.left_img = self.get_tkinter_image(self.current_left_page)
        if self.left_img:
            self.left_label.config(image=self.left_img, text="")
        else:
            self.left_label.config(image="", text="End of Score")

        # Render Right
        self.right_img = self.get_tkinter_image(self.current_left_page + 1)
        if self.right_img:
            self.right_label.config(image=self.right_img, text="")
        else:
            self.right_label.config(image="", text="")

        elapsed = (time.time() - start_time) * 1000
        print(f"Display update latency: {elapsed:.2f} ms")

    def next_pages(self):
        if self.current_left_page + 2 < self.total_pages:
            self.current_left_page += 2
            self.update_displays()

    def prev_pages(self):
        if self.current_left_page - 2 >= 0:
            self.current_left_page -= 2
            self.update_displays()

if __name__ == "__main__":
    PDF_FILE = "sample_score.pdf" 
    
    root = tk.Tk()
    root.geometry("1200x800") 
    
    app = CachedDualScreenReader(root, PDF_FILE)
    root.mainloop()