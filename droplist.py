from pathlib import Path
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QAbstractItemView

class DropList(QListWidget):
    # Easiest: use signal without arguments
    filesChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.allowed_ext = set()
        self.setAcceptDrops(True)
        self.setDragEnabled(False)
        self.setDropIndicatorShown(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

    def _is_allowed(self, path: Path) -> bool:
        return (not self.allowed_ext) or (path.suffix.lower() in self.allowed_ext)

    def dragEnterEvent(self, e):
        self._accept_if_ok(e)

    # >>> ADD: also accept during movement
    def dragMoveEvent(self, e):
        self._accept_if_ok(e)

    def _accept_if_ok(self, e):
        md = e.mimeData()
        if md.hasUrls():
            for url in md.urls():
                p = Path(url.toLocalFile())
                if p.is_file() and self._is_allowed(p):
                    e.acceptProposedAction()
                    return
        e.ignore()

    def dropEvent(self, e):
        md = e.mimeData()
        if not md.hasUrls():
            e.ignore()
            return
        
        existing_paths = { self.item(i).data(Qt.UserRole) for i in range(self.count()) }

        added = 0
        for url in md.urls():
            p = Path(url.toLocalFile())
            if p.is_file() and self._is_allowed(p):
                sp = str(p)
                if sp not in existing_paths:
                    it = QListWidgetItem(p.name)      # show file name only
                    it.setData(Qt.UserRole, sp)       # hide full path
                    self.addItem(it)
                    added += 1

        if added:
            self.filesChanged.emit()    
            e.acceptProposedAction()
        else:
            e.ignore()

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            for it in self.selectedItems():
                self.takeItem(self.row(it))
            self.filesChanged.emit()
        else:
            super().keyPressEvent(e)
    
        # Right click menu
    def contextMenuEvent(self, e):
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        actRemove = menu.addAction("Remove selected")
        actClear  = menu.addAction("Clear all")
        a = menu.exec(e.globalPos())
        if a == actRemove:
            for it in self.selectedItems():
                self.takeItem(self.row(it))
            self.filesChanged.emit()
        elif a == actClear:
            self.clear()
            self.filesChanged.emit()

    def clear(self):
        super().clear()
        self.filesChanged.emit()
