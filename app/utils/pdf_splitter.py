import os
import tempfile
from PyPDF2 import PdfReader, PdfWriter
from fastapi import UploadFile
from typing import List
from pathlib import Path
from app.exceptions import PDFError

class PDFSplitter:
    MAX_PAGES = 3
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB in bytes

    @staticmethod
    async def split_if_needed(file: UploadFile) -> List[Path]:
        """Split PDF file if it exceeds MAX_PAGES or MAX_FILE_SIZE, returns list of temporary file paths"""
        content = await file.read()
        file_size = len(content)
        

        # Create a unique session directory under tmp
        session_dir = tempfile.mkdtemp(prefix='pdf_split_')
        
        # Store original file with its original name
        original_filename = Path(file.filename).name
        original_file_path = os.path.join(session_dir, original_filename)
        with open(original_file_path, 'wb') as temp_upload:
            temp_upload.write(content)
            temp_upload_path = original_file_path

        try:
            # Read the PDF
            reader = PdfReader(temp_upload_path)
            total_pages = len(reader.pages)

            # Calculate number of parts needed based on page limit first
            page_parts = (total_pages + PDFSplitter.MAX_PAGES - 1) // PDFSplitter.MAX_PAGES
            num_parts = page_parts

            # If file size per part would exceed limit, increase number of parts
            estimated_size_per_part = file_size / num_parts
            if estimated_size_per_part > PDFSplitter.MAX_FILE_SIZE:
                size_parts = (file_size + PDFSplitter.MAX_FILE_SIZE - 1) // PDFSplitter.MAX_FILE_SIZE
                num_parts = max(size_parts, page_parts)

            # If no splitting is needed, return as is
            if num_parts == 1:
                await file.seek(0)  # Reset file pointer
                return [Path(temp_upload_path)]

            # Calculate initial split based on pages
            pages_per_part = total_pages // num_parts
            remaining_pages = total_pages % num_parts

            # Initialize list for split files
            temp_files = []

            current_page = 0
            base_name = Path(file.filename).stem

            # Split into parts while monitoring actual file sizes
            for i in range(num_parts):
                writer = PdfWriter()
                pages_this_part = pages_per_part + (1 if i < remaining_pages else 0)
                part_size = 0
                pages_added = 0

                # Add pages while checking size
                while pages_added < pages_this_part and current_page < total_pages:
                    page = reader.pages[current_page]
                    writer.add_page(page)
                    current_page += 1
                    pages_added += 1

                    # Check estimated size after adding each page
                    if pages_added > 1:
                        # Create a temporary file to check actual size
                        temp_check = tempfile.NamedTemporaryFile(delete=False)
                        writer.write(temp_check)
                        temp_check.close()
                        part_size = os.path.getsize(temp_check.name)
                        os.unlink(temp_check.name)

                        if part_size > PDFSplitter.MAX_FILE_SIZE:
                            # Remove the last page if size exceeds limit
                            writer = PdfWriter()
                            for j in range(pages_added - 1):
                                writer.add_page(reader.pages[current_page - pages_added + j])
                            current_page -= 1
                            pages_added -= 1
                            break

                # Save the split part
                # Create split files in the same session directory
                split_filename = f"{Path(file.filename).stem}_{i+1}.pdf"
                split_file_path = os.path.join(session_dir, split_filename)
                with open(split_file_path, 'wb') as temp_file:
                    writer.write(temp_file)
                temp_files.append(Path(split_file_path))

                # If we've processed all pages, break
                if current_page >= total_pages:
                    break

            return temp_files

        except Exception as e:
            # Clean up temporary upload file in case of error
            os.unlink(temp_upload_path)
            raise PDFError(f"PDF splitting error: {str(e)}")

    @staticmethod
    def cleanup_temp_files(temp_files: List[Path]):
        """Clean up temporary files after processing"""
        for temp_file in temp_files:
            try:
                if temp_file.exists():
                    temp_file.unlink()
            except Exception:
                pass  # Best effort cleanup