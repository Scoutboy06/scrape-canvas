import html2text
#!bin/python3
from dotenv import load_dotenv
import os
import re

from pathvalidate import sanitize_filename
from canvasapi import Canvas
from canvasapi.course import Course
from canvasapi.exceptions import Unauthorized, ResourceDoesNotExist, Forbidden
from canvasapi.file import File
from canvasapi.module import Module, ModuleItem


def extract_files(text):
    text_search = re.findall("/files/(\\d+)", text, re.IGNORECASE)
    groups = set(text_search)
    return groups


def write_html_or_md(content, base_path, title):
    """Write content as .md if enabled, else as .html. Never keep .html if .md is written."""
    convert = os.getenv("CONVERT_HTML_TO_MD", "true").lower() == "true"
    safe_title = sanitize_filename(title)
    if convert:
        md_path = os.path.join(base_path, safe_title + ".md")
        try:
            md_content = html2text.html2text(content)
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(md_content)
        except Exception as e:
            print(f"Failed to convert {title} to markdown: {e}")
    else:
        html_path = os.path.join(base_path, safe_title + ".html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(content)

def get_course_files(course):
    modules = course.get_modules()

    files_downloaded = set() # Track downloaded files for this course to avoid duplicates

    for module in modules:
        module: Module = module
        module_items = module.get_module_items()
        for item in module_items:
            item: ModuleItem = item
            
            try:
                path = f"{output}/" \
                    f"{sanitize_filename(course.name)}/" \
                    f"{sanitize_filename(module.name)}/"
            except Exception as e:
                print(e)
                continue
            if not os.path.exists(path):
                os.makedirs(path)

            item_type = item.type
            print(f"{course.name} - "
                  f"{module.name} - "
                  f"{item.title} ({item_type})")

            if item_type == "File":
                file = canvas.get_file(item.content_id)
                files_downloaded.add(item.content_id)
                file.download(path + sanitize_filename(file.filename))
            elif item_type == "Page":
                page = course.get_page(item.page_url)
                write_html_or_md(page.body or "", path, item.title)
                files = extract_files(page.body or "")
                for file_id in files:
                    if file_id in files_downloaded:
                        continue
                    try:
                        file = course.get_file(file_id)
                        files_downloaded.add(file_id)
                        file.download(path + sanitize_filename(file.filename))
                    except ResourceDoesNotExist:
                        pass
            elif item_type == "ExternalUrl":
                url = item.external_url
                with open(path + sanitize_filename(item.title) + ".url", "w") as f:
                    f.write("[InternetShortcut]\n")
                    f.write("URL=" + url)
            elif item_type == "Assignment":
                assignment = course.get_assignment(item.content_id)
                write_html_or_md(assignment.description or "", path, item.title)
                files = extract_files(assignment.description or "")
                for file_id in files:
                    if file_id in files_downloaded:
                        continue
                    try:
                        file = course.get_file(file_id)
                        files_downloaded.add(file_id)
                        file.download(path + sanitize_filename(file.filename))
                    except ResourceDoesNotExist:
                        pass
                    except Unauthorized:
                        pass
                    except Forbidden:
                        pass

    try:
        files = course.get_files()
        for file in files:
            file: File = file
            if not file.id in files_downloaded:
                print(f"{course.name} - {file.filename}")
                path = f"{output}/{sanitize_filename(course.name)}/" \
                    f"{sanitize_filename(file.filename)}"
                file.download(path)
    except Unauthorized:
        pass
    except Forbidden:
        pass


if __name__ == "__main__":
    # Load environment variables from .env file
    load_dotenv()

    url = os.getenv("URL")
    token = os.getenv("TOKEN")
    output = os.getenv("OUTPUT", "./output/").rstrip("/") + "/"
    courses_env = os.getenv("COURSES", "all")

    if not url or not token:
        print("Missing URL or TOKEN in environment variables. Please check your .env file.")
        exit(1)


    # Ensure .gitignore in output folder
    output_gitignore = os.path.join(output, ".gitignore")
    os.makedirs(output, exist_ok=True)
    if not os.path.exists(output_gitignore):
        with open(output_gitignore, "w") as f:
            f.write("*\n")

    canvas = Canvas(url, token)

    # Select courses to scrape, default to all
    if courses_env != "all":
        courses = []
        ids = courses_env.split(",")
        for id in ids:
            courses.append(canvas.get_course(int(id)))
    else:
        courses = canvas.get_courses()

    # Perform scrape
    for course in courses:
        course: Course = course
        get_course_files(course)
