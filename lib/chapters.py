import random

class ChapterMaker(object):
    def __init__(self):
        self.chapters = {}
        self.uid_diff = 1000000000
        self.uid_begin = 0
    def add(self, chapters):
        chapters.update(self.chapters)
        self.chapters = chapters
    def update(self, chapters):
        self.chapters.update(chapters)
    def get_uid(self):
        uid = str(random.randrange(self.uid_begin, self.uid_begin + self.uid_diff))
        self.uid_begin += self.uid_diff
        return uid
    def make_chapter(self, name, time):
        lines = []
        lines.append("    <ChapterAtom>")
        lines.append("      <ChapterUID>%s</ChapterUID>" % self.get_uid())
        lines.append("      <ChapterFlagHidden>0</ChapterFlagHidden>")
        lines.append("      <ChapterFlagEnabled>1</ChapterFlagEnabled>")
        lines.append("      <ChapterTimeStart>%s</ChapterTimeStart>" % intToTime(time))
        lines.append("      <ChapterDisplay>")
        lines.append("        <ChapterString>%s</ChapterString>" % name)
        lines.append("        <ChapterLanguage>eng</ChapterLanguage>")
        lines.append("      </ChapterDisplay>")
        lines.append("    </ChapterAtom>")
        return lines
    def __str__(self):
        chapters = sorted(self.chapters.items(), key=lambda x: x[1])
        lines = []
        lines.append("<?xml version='1.0' encoding='UTF-8'?>")
        lines.append("")
        lines.append("<!-- <!DOCTYPE Tags SYSTEM \"matroskatags.dtd\"> -->")
        lines.append("")
        lines.append("<Chapters>")
        lines.append("  <EditionEntry>")
        lines.append("    <EditionFlagHidden>0</EditionFlagHidden>")
        lines.append("    <EditionFlagDefault>0</EditionFlagDefault>")
        lines.append("    <EditionUID>%s</EditionUID>" % self.get_uid())
        for name, time in chapters:
            lines.extend(self.make_chapter(name, time))
        lines.append("  </EditionEntry>")
        lines.append("</Chapters>")
        return "\n".join(lines)

