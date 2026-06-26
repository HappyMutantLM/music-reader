import fitz  # PyMuPDF
import tkinter as tk
from PIL import Image, ImageTk
import sys

class DualScreenReader:
    def __init__(self, root, pdf_path):
        self.root = root
        self.root.title("DIY GVIDO Prototype")
        
        # Load the PDF document
        try:
            self.doc = fitz.open(pdf_path)
            self.total_pages = len(self.doc)
        except Exception as e:
            print(f"Error loading PDF: {e}")
            sys.exit(1)
            
        # Start at page 0 (Left screen = Page 0, Right screen = Page 1)
        self.current_left_page = 0
        
        # Set up the UI layout (Side-by-side screens)
        self.left_label = tk.Label(root, bg="grey")
        self.left_label.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)
        
        self.right_label = tk.Label(root, bg="grey")
        self.right_label.pack(side=tk.RIGHT, expand=True, fill=tk.BOTH)
        
        # Bind keys for page turning (Simulating a foot pedal)
        self.root.bind("<Right>", lambda e: self.next_pages())
        self.root.bind("<Left>", lambda e: self.prev_pages())
        self.root.bind("<space>", lambda e: self.next_pages())
        
        # Render the initial pages
        self.update_displays()

    def render_page(self, page_num):
        """Renders a PDF page to a Tkinter-compatible image."""
        if page_num < 0 or page_num >= self.total_pages:
            # Return a blank white image if the page doesn't exist
            return None
            
        page = self.doc[page_num]
        
        # Set target resolution (adjust to match your monitor/future e-ink aspect ratio)
        zoom = 1.5  
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        
        # Convert Pixmap to PIL Image, then to ImageTk
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        return ImageTk.PhotoImage(img)

    def update_displays(self):
        """Updates both screens based on the current page state."""
        # Render Left Page (Page N)
        self.left_img = self.render_page(self.current_left_page)
        if self.left_img:
            self.left_label.config(image=self.left_img)
        else:
            self.left_label.config(image="", text="End of Score")

        # Render Right Page (Page N + 1)
        self.right_img = self.render_page(self.current_left_page + 1)
        if self.right_img:
            self.right_label.config(image=self.right_img)
        else:
            self.right_label.config(image="", text="")

    def next_pages(self):
        """Advances the book by 2 pages."""
        if self.current_left_page + 2 < self.total_pages:
            self.current_left_page += 2
            self.update_displays()
            print(f"Advanced to pages {self.current_left_page} & {self.current_left_page + 1}")

    def prev_pages(self):
        """Goes back by 2 pages."""
        if self.current_left_page - 2 >= 0:
            self.current_left_page -= 2
            self.update_displays()
            print(f"Returned to pages {self.current_left_page} & {self.current_left_page + 1}")

if __name__ == "__main__":
    # Replace with a path to one of your sheet music PDFs
    PDF_FILE = "sample_score.pdf" 
    
    root = tk.Tk()
    # Make it large enough to see side-by-side pages
    root.geometry("1200x800") 
    
    app = DualScreenReader(root, PDF_FILE)
    root.mainloop()