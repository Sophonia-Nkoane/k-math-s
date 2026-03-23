from PySide6.QtWidgets import QLabel, QHBoxLayout
from presentation.styles.colors import TEXT_COLOR
from presentation.components.rounded_field  import RoundedPlainTextField, RoundedDropdown, RoundedCheckBox
from presentation.components.buttons import ButtonFactory

class SearchBar:
    def __init__(self, parent):
        self.parent = parent
        self.layout = QHBoxLayout()
        self.setup_search_components()

    def setup_search_components(self):
        # Search Bar
        search_label = QLabel("Search:")
        search_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        self.search_entry = RoundedPlainTextField()
        self.search_entry.setPlaceholderText("Name, Surname or Acc...")
        self.search_entry.textChanged.connect(self.parent.filter_displayed_learners)
        
        clear_search_btn = ButtonFactory.create_clear_button("Clear")
        clear_search_btn.clicked.connect(self.search_entry.clear)

        # Status Filter
        status_filter_label = QLabel("Filter Status:")
        status_filter_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        self.status_filter_combo = RoundedDropdown()
        self.status_filter_combo.addItems(["All", "Active", "Paused"])
        self.status_filter_combo.currentIndexChanged.connect(self.parent.filter_displayed_learners)

        # Grade Filter
        grade_filter_label = QLabel("Filter by Grade:")
        grade_filter_label.setStyleSheet(f"color: {TEXT_COLOR()};")
        self.grade_filter_combo = RoundedDropdown()
        self.grade_filter_combo.addItem("All")
        self.grade_filter_combo.addItems([str(g) for g in range(1, 13)])
        self.grade_filter_combo.setEnabled(False)
        self.grade_filter_combo.currentIndexChanged.connect(self.parent.filter_displayed_learners)

        # Grade Filter Checkbox
        self.grade_filter_checkbox = RoundedCheckBox("Activate Grade Filter")
        self.grade_filter_checkbox.setChecked(False)
        self.grade_filter_checkbox.stateChanged.connect(
            lambda state: self.parent.toggle_grade_filter(state)
        )

        # Add components to layout
        self.layout.addWidget(search_label)
        self.layout.addWidget(self.search_entry)
        self.layout.addWidget(clear_search_btn)
        self.layout.addSpacing(20)
        self.layout.addWidget(status_filter_label)
        self.layout.addWidget(self.status_filter_combo)
        self.layout.addWidget(grade_filter_label)
        self.layout.addWidget(self.grade_filter_combo)
        self.layout.addWidget(self.grade_filter_checkbox)
        self.layout.addStretch()
