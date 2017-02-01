
import os
import sys
import string
import wx
import wx.grid as gridlib
import sqlite3
import psycopg2
import psycopg2.extras

#---------------------------------------------------------------------------
# Logging engine class

class Log:
    def WriteText(self, text):
        if text[-1:] == '\n':
            text = text[:-1]
        wx.LogMessage(text)
    write = WriteText


#---------------------------------------------------------------------------
# Main frame class

class MainFrame(wx.Frame):
    def __init__(self, parent):
        wx.Frame.__init__(self, parent, -1, "ETL CodeGen Metadata Editor 0.5", size=(1152,700))
        self.CentreOnScreen()


#---------------------------------------------------------------------------

class ETLCodeGenApp(wx.App):
    def OnInit(self):
        wx.Log.SetActiveTarget(wx.LogStderr())
        self.log = Log()

        #---------------------------------------------------------------------------
        # Initializing the metadata database

        self.db_filename = 'etl_metadata.db'
        self.InitDatabase()

        #---------------------------------------------------------------------------
        # Creating main frame (window)

        self.frame = MainFrame(None)
        self.frame.Bind(wx.EVT_CLOSE, self.OnFrameClose)
        self.frame.CreateStatusBar()

        #---------------------------------------------------------------------------
        # Creating main menu

        fileMenu = wx.Menu()

        item = fileMenu.Append(wx.ID_ABOUT, "&About", "Information about the program!")
        self.Bind(wx.EVT_MENU, self.OnMenuAbout, item)

        fileMenu.AppendSeparator()

        item = fileMenu.Append(wx.ID_ANY, "&Refresh\tCtrl-R", "Refresh tree")
        self.Bind(wx.EVT_MENU, self.OnMenuRefresh, item)

        fileMenu.AppendSeparator()

        item = fileMenu.Append(wx.ID_ANY, "&Generate DDL code\tCtrl-D", "Generate DDL code for related tables")
        self.Bind(wx.EVT_MENU, self.OnMenuGenerateDDL, item)

        item = fileMenu.Append(wx.ID_ANY, "&Generate ETL code\tCtrl-G", "Generate ETL code to load the tables")
        self.Bind(wx.EVT_MENU, self.OnMenuGenerateETL, item)

        fileMenu.AppendSeparator()

        item = fileMenu.Append(wx.ID_EXIT, "E&xit\tCtrl-Q", "Exit program")
        self.Bind(wx.EVT_MENU, self.OnMenuExit, item)

        menuBar = wx.MenuBar()

        menuBar.Append(fileMenu, "&File")

        self.frame.SetMenuBar(menuBar)


        #---------------------------------------------------------------------------
        # Create the main splitter window (to be split vertically)

        splitter = wx.SplitterWindow(self.frame, -1, style = (wx.SP_LIVE_UPDATE | wx.SP_3D))
        splitter.SetMinimumPaneSize(100)

        #---------------------------------------------------------------------------
        # Building the grid

        panel = wx.Panel(splitter, -1)

        self.grid = gridlib.Grid(panel)
        self.grid.SetDefaultRowSize(25)
        self.grid.SetRowLabelSize(0)
        self.grid.deletedItems = []
        self.grid.hasUsavedChanges = False
        self.grid.Bind(gridlib.EVT_GRID_EDITOR_SHOWN, self.OnGridCellChanged) # EVT_GRID_CELL_CHANGED/EVT_GRID_CELL_CHANGING don't work on Linux
        #self.grid.Bind(gridlib.EVT_GRID_CELL_CHANGED, self.OnGridCellChanged)
        self.grid.Bind(gridlib.EVT_GRID_CELL_RIGHT_CLICK, self.OnGridRightClick)

        self.grid.CreateGrid(0, 0)

        self.buttonAdd = wx.Button(panel, label="Add item", size=(150,25))
        self.Bind(wx.EVT_BUTTON, self.OnButtonAddItem, self.buttonAdd)

        self.buttonImport = wx.Button(panel, label="Import item", size=(150,25))
        self.Bind(wx.EVT_BUTTON, self.OnButtonImportItem, self.buttonImport)

        self.buttonDelete = wx.Button(panel, label="Delete item", size=(150,25))
        self.Bind(wx.EVT_BUTTON, self.OnButtonDeleteItem, self.buttonDelete)

        self.buttonSave = wx.Button(panel, label="Save changes", size=(150,25))
        self.Bind(wx.EVT_BUTTON, self.OnButtonSaveChanges, self.buttonSave)

        self.buttonSaveAndRefresh = wx.Button(panel, label="Save and refresh", size=(150,25))
        self.Bind(wx.EVT_BUTTON, self.OnButtonSaveAndRefresh, self.buttonSaveAndRefresh)

        sizerVertMain = wx.BoxSizer(wx.VERTICAL)
        sizerHorzButtons = wx.BoxSizer(wx.HORIZONTAL)

        sizerHorzButtons.Add(self.buttonAdd, 0, wx.ALL, 5)
        sizerHorzButtons.Add(self.buttonImport, 0, wx.ALL, 5)
        sizerHorzButtons.Add(self.buttonDelete, 0, wx.ALL, 5)
        sizerHorzButtons.Add(self.buttonSave, 0, wx.ALL, 5)
        sizerHorzButtons.Add(self.buttonSaveAndRefresh, 0, wx.ALL, 5)

        sizerVertMain.Add(self.grid, 1, wx.EXPAND)
        sizerVertMain.Add(sizerHorzButtons, 0, wx.ALIGN_BOTTOM)

        panel.SetSizerAndFit(sizerVertMain)


        #---------------------------------------------------------------------------
        # Building the tree

        self.tree = wx.TreeCtrl(splitter, wx.ID_ANY, wx.DefaultPosition, (0,0), wx.TR_HAS_BUTTONS)
        # wx.TR_EDIT_LABELS, wx.TR_MULTIPLE, wx.TR_HIDE_ROOT

        # Images size tuple
        imageSize = (16,16)
        imageList = wx.ImageList(imageSize[0], imageSize[1])
        self.folderIdx     = imageList.Add(wx.ArtProvider_GetBitmap(wx.ART_FOLDER,      wx.ART_OTHER, imageSize))
        self.folderOpenIdx = imageList.Add(wx.ArtProvider_GetBitmap(wx.ART_FOLDER_OPEN, wx.ART_OTHER, imageSize))
        self.fileIdx       = imageList.Add(wx.ArtProvider_GetBitmap(wx.ART_NORMAL_FILE, wx.ART_OTHER, imageSize))
        self.fileOpenIdx   = imageList.Add(wx.ArtProvider_GetBitmap(wx.ART_FILE_OPEN,   wx.ART_OTHER, imageSize))

        self.tree.SetImageList(imageList)
        self.imageList = imageList # Segfaults without it!

        self.Bind(wx.EVT_TREE_SEL_CHANGING, self.OnTreeSelChanging, self.tree)
        self.Bind(wx.EVT_TREE_SEL_CHANGED, self.OnTreeSelChanged, self.tree)

        self.RefreshTree()


        #---------------------------------------------------------------------------
        # Aligning the controls

        splitter.SplitVertically(self.tree, panel, 250)


        #---------------------------------------------------------------------------
        # Creating tree popup menu

        self.popupMenu = wx.Menu()

        item = self.popupMenu.Append(wx.ID_ANY, "&Add item", "Add new item")
        self.Bind(wx.EVT_MENU, self.OnButtonAddItem, item)

        self.popupMenu.AppendSeparator()

        item = self.popupMenu.Append(wx.ID_ANY, "&Delete item", "Delete existing item")
        self.Bind(wx.EVT_MENU, self.OnButtonDeleteItem, item)


        #---------------------------------------------------------------------------
        # Showing the main frame

        self.tree.SetFocus()
        self.frame.Show(True)
        self.SetTopWindow(self.frame)
        
        return True


    #---------------------------------------------------------------------------
    # Creating the database if it doesn't exist yet

    def InitDatabase(self):
        schema_filename = 'etl_metadata_ddl.sql'

        db_is_new = not os.path.exists(self.db_filename)

        with sqlite3.connect(self.db_filename) as conn:
            if db_is_new:
                self.log.WriteText('Creating schema')

                with open(schema_filename, 'rt') as f:
                    schema = f.read()
                conn.executescript(schema)

                self.log.WriteText('Inserting initial data')

                insert_data = [
                    [1, 'Sample DWH'],
                ]

                conn.executemany("""
                    insert into project (project_id, project_name)
                    values (?, ?)
                    """, insert_data)

                conn.commit()

            else:
                self.log.WriteText('Database exists, assume schema does, too.')


    #---------------------------------------------------------------------------
    # Returning the resulting dataset of any query

    def GetDataset(self, query):
        with sqlite3.connect(self.db_filename) as conn:
            self.log.WriteText('Selecting data: {0}'.format(query))

            cur = conn.cursor()
            meta = cur.execute(query + ' limit 0')

            columnNames = []
            columnNamesHuman = []

            for i in meta.description:
                columnNames.append(i[0])
                columnNamesHuman.append(i[0].title().replace('_',' '))

            dataset = cur.execute(query)

            data = []

            # Adding the first two rows as original and formatted column names
            data.append(columnNames)
            data.append(columnNamesHuman)

            # Adding the query results
            for row in dataset:
                data_row = []
                for i in range(len(row)):
                    if row[i] != None:
                        data_row.append(row[i])
                    else:
                        data_row.append('')
                data.append(data_row)

        print data
        return data


    #---------------------------------------------------------------------------
    # Returning the resulting dataset of any query

    def GetDataAsList(self, query):
        with sqlite3.connect(self.db_filename) as conn:
            self.log.WriteText('Selecting data: {0}'.format(query))

            cur = conn.cursor()
            dataset = cur.execute(query)

            data = []

            # Adding the query results to a list
            for row in dataset:
                if row[0] != None:# and row[0] != "null":
                    data.append(row[0])

        #print data
        return data


    #---------------------------------------------------------------------------
    # Returning the resulting dataset of any query

    def SaveDataset(self, treeItemData, dataset, isOverwrite, deletedItems):
        with sqlite3.connect(self.db_filename) as conn:
            self.log.WriteText('Saving data for {table}'.format(**treeItemData))
            print treeItemData
            print dataset
            print deletedItems

            table = treeItemData['table']

            if table != 'stage_column':
                if len(deletedItems) > 0:
                    deletedItemsString = ''

                    for delId in deletedItems:
                        deletedItemsString += delId + ','

                    deletedItemsString = deletedItemsString[:-1]
                    print deletedItemsString

                    if table == 'stage_table':
                        conn.execute("""
                            delete from stage_column
                            where stage_table_id in ({0})
                        """.format(deletedItemsString))
                    
                    elif table == 'stage_db':
                        conn.execute("""
                            delete from stage_column
                            where stage_table_id in (
                                select stage_table_id
                                from stage_table 
                                where stage_db_id in ({0})
                            )
                        """.format(deletedItemsString))
                        
                        conn.execute("""
                            delete from stage_table
                            where stage_db_id in ({0})
                        """.format(deletedItemsString))
                    
                    elif table == 'project':
                        conn.execute("""
                            delete from stage_column
                            where stage_table_id in (
                                select stage_table_id
                                from stage_table 
                                where stage_db_id in (
                                    select stage_db_id
                                    from stage_db
                                    where project_id in ({0})
                                )
                            )
                        """.format(deletedItemsString))
                        
                        conn.execute("""
                            delete from stage_table
                            where stage_db_id in (
                                select stage_db_id
                                from stage_db
                                where project_id in ({0})
                            )
                        """.format(deletedItemsString))
                        
                        conn.execute("""
                            delete from stage_db
                            where project_id in ({0})
                        """.format(deletedItemsString))

            if isOverwrite:
                conn.execute('delete from {table} {where}'.format(**treeItemData))

            conn.executemany('insert into {table} ({columns}) values ({placeholders})'.format(**treeItemData), dataset)

            conn.commit()



    #---------------------------------------------------------------------------
    # Refreshing tree items from database

    def RefreshTree(self):
        self.log.WriteText("RefreshTree")
        self.tree.DeleteAllItems()

        table = 'project'
        where = ''
        parent_id = 0
        rootProjectsItem = self.tree.AddRoot("Projects")
        projectsDataset = self.GetDataset('select * from {0} {1}'.format(table, where))

        columns = ''
        placeholders = ''

        for colName in projectsDataset[0]:#[1:]:
            columns += colName + ','
            placeholders += '?,'

        columns = columns[:-1]
        placeholders = placeholders[:-1]

        self.tree.SetPyData(rootProjectsItem, {"table": table, "where": where, "columns": columns, "placeholders": placeholders, "parent_id": parent_id})
        self.tree.SetItemImage(rootProjectsItem, self.folderIdx, wx.TreeItemIcon_Normal)
        self.tree.SetItemImage(rootProjectsItem, self.folderOpenIdx, wx.TreeItemIcon_Expanded)

        for projectItem in projectsDataset[2:]:
            table = 'stage_db'
            where = 'where project_id = {0}'
            parent_id = projectItem[0]
            projectTreeItem = self.tree.AppendItem(rootProjectsItem, projectItem[1])
            stageDbDataset = self.GetDataset('select * from {0} {1}'.format(table, where.format(parent_id)))

            columns = ''
            placeholders = ''

            for colName in stageDbDataset[0]:#[1:]:
                columns += colName + ','
                placeholders += '?,'

            columns = columns[:-1]
            placeholders = placeholders[:-1]

            self.tree.SetPyData(projectTreeItem, {"table": table, "where": where.format(projectItem[0]), "columns": columns, "placeholders": placeholders, "parent_id": parent_id})
            self.tree.SetItemImage(projectTreeItem, self.folderIdx, wx.TreeItemIcon_Normal)
            self.tree.SetItemImage(projectTreeItem, self.folderOpenIdx, wx.TreeItemIcon_Expanded)

            for stageDbItem in stageDbDataset[2:]:
                table = 'stage_table'
                where = 'where stage_db_id = {0}'
                parent_id = stageDbItem[0]
                stageDbTreeItem = self.tree.AppendItem(projectTreeItem, stageDbItem[2])
                stageTableDataset = self.GetDataset('select * from {0} {1} order by target_entity_name'.format(table, where.format(parent_id)))

                columns = ''
                placeholders = ''

                for colName in stageTableDataset[0]:#[1:]:
                    columns += colName + ','
                    placeholders += '?,'

                columns = columns[:-1]
                placeholders = placeholders[:-1]

                self.tree.SetPyData(stageDbTreeItem, {"table": table, "where": where.format(stageDbItem[0]), "columns": columns, "placeholders": placeholders, "parent_id": parent_id})
                self.tree.SetItemImage(stageDbTreeItem, self.folderIdx, wx.TreeItemIcon_Normal)
                self.tree.SetItemImage(stageDbTreeItem, self.folderOpenIdx, wx.TreeItemIcon_Expanded)

                for stageTableItem in stageTableDataset[2:]:
                    table = 'stage_column'
                    where = 'where stage_table_id = {0}'
                    parent_id = stageTableItem[0]
                    # Adding entity subitem and stage table name
                    if stageTableItem[7] != None and stageTableItem[7] != '':
                        targetTableName = stageTableItem[5] + '.' + stageTableItem[6] + '_' + stageTableItem[7] + ' (' + stageTableItem[2] + '.' + stageTableItem[3] + ')'
                    else:
                        targetTableName = stageTableItem[5] + '.' + stageTableItem[6] + ' (' + stageTableItem[2] + '.' + stageTableItem[3] + ')'
                    stageTableTreeItem = self.tree.AppendItem(stageDbTreeItem, targetTableName)
                    stageColumnDataset = self.GetDataset('select * from {0} {1}'.format(table, where.format(parent_id)))

                    columns = ''
                    placeholders = ''

                    for colName in stageColumnDataset[0]:#[1:]:
                        columns += colName + ','
                        placeholders += '?,'

                    columns = columns[:-1]
                    placeholders = placeholders[:-1]

                    self.tree.SetPyData(stageTableTreeItem, {"table": table, "where": where.format(stageTableItem[0]), "columns": columns, "placeholders": placeholders, "parent_id": parent_id})
                    self.tree.SetItemImage(stageTableTreeItem, self.fileIdx, wx.TreeItemIcon_Normal)
                    #self.tree.SetItemImage(stageTableTreeItem, self.fileOpenIdx, wx.TreeItemIcon_Selected)

        self.tree.Expand(rootProjectsItem)
        self.tree.SelectItem(rootProjectsItem, False)
        self.tree.SelectItem(rootProjectsItem, True)


    #---------------------------------------------------------------------------
    # Refreshing grid from database

    def RefreshGrid(self):
        self.log.WriteText("RefreshGrid")
        if self.grid.treeItemData != None:
            table = self.grid.treeItemData['table']
            where = self.grid.treeItemData['where']

            if (table == 'stage_column'):
                order = 'order by target_ordinal_pos'
            elif (table == 'stage_table'):
                order = 'order by target_entity_name'
            else:
                order = ''

            if (table == 'stage_table') or (table == 'stage_column'):
                self.buttonImport.SetLabel('Import ' + table.title().replace('_',' '))
                self.buttonImport.Enable()
            else:
                self.buttonImport.SetLabel('Import not available')
                self.buttonImport.Disable()

            self.buttonAdd.SetLabel('Add ' + table.title().replace('_',' '))
            self.buttonDelete.SetLabel('Delete ' + table.title().replace('_',' '))

            gridDataset = self.GetDataset('select * from {0} {1} {2}'.format(table, where, order))
            print gridDataset

            # Clean the grid
            if self.grid.GetNumberCols() > 0:
                self.grid.DeleteCols(0,self.grid.GetNumberCols())
            if self.grid.GetNumberRows() > 0:
                self.grid.DeleteRows(0,self.grid.GetNumberRows())

            # Adding new columns
            self.grid.AppendCols(len(gridDataset[1]))
            self.grid.AppendRows(len(gridDataset[2:]))

            # Assigning column labels
            for i in range(len(gridDataset[1])):
                self.grid.SetColLabelValue(i, gridDataset[1][i])

            for rowIdx, rowValues in enumerate(gridDataset[2:]):
                for colIdx, cellValue in enumerate(rowValues):
                    self.grid.SetCellValue(rowIdx, colIdx, str(cellValue))

            self.UpdateGridEditors()
            self.UpdateGridSelectors()
            self.grid.AutoSizeColumns()
            self.grid.deletedItems = []
            self.grid.hasUsavedChanges = False


    def UpdateGridEditors(self):
        self.log.WriteText("UpdateGridEditors")
        for rowIdx in range(self.grid.GetNumberRows()):
            for colIdx in range(self.grid.GetNumberCols()):
                currentColLabel = self.grid.GetColLabelValue(colIdx)

                if (colIdx == 0) or (currentColLabel.endswith(' Id')):
                    self.grid.SetReadOnly(rowIdx, colIdx, True)
                    self.grid.SetCellBackgroundColour(rowIdx, colIdx, wx.LIGHT_GREY)

                if currentColLabel.endswith(' Pos'):
                    self.grid.SetCellEditor(rowIdx, colIdx, gridlib.GridCellNumberEditor(0,999999))

                if currentColLabel.startswith('Is '):
                    self.grid.SetCellEditor(rowIdx, colIdx, gridlib.GridCellBoolEditor())
                    self.grid.SetCellRenderer(rowIdx, colIdx, gridlib.GridCellBoolRenderer())

        #self.grid.SetCellFont(0, 0, wx.Font(16, wx.ROMAN, wx.ITALIC, wx.NORMAL))
        #self.grid.SetCellTextColour(1, 1, wx.RED)
        #self.grid.SetCellBackgroundColour(2, 2, wx.CYAN)

        #self.grid.SetCellEditor(8, 0, gridlib.GridCellChoiceEditor(['aaa','bbb'], allowOthers=True))
        #self.grid.SetCellValue(8, 0, 'aaa')


    def UpdateGridSelectors(self):
        self.log.WriteText("UpdateGridSelectors")

        # Getting FK Entities List
        selectorFkEntityList = self.GetDataAsList('''
            select distinct
                t.target_entity_name
            from stage_table t
                join stage_db d on d.stage_db_id = t.stage_db_id
                join project p on p.project_id = d.project_id
            where p.project_id = (select d.project_id from stage_table t join stage_db d on d.stage_db_id = t.stage_db_id where t.stage_table_id = {parent_id})
            order by 1'''.format(parent_id = str(self.grid.treeItemData['parent_id'])))

        if len(selectorFkEntityList) == 0 or selectorFkEntityList[0] != '':
            selectorFkEntityList.insert(0, '')

        for rowIdx in range(self.grid.GetNumberRows()):

            currentTargetEntity = ''
            currentTargetEntitySubname = ''

            # First, scan all columns to get current FK Entity
            for colIdx in range(self.grid.GetNumberCols()):
                currentColLabel = self.grid.GetColLabelValue(colIdx)
                if currentColLabel == 'Fk Entity Name':
                    currentTargetEntity = self.grid.GetCellValue(rowIdx, colIdx)
                if currentColLabel == 'Fk Entity Subname':
                    currentTargetEntitySubname = self.grid.GetCellValue(rowIdx, colIdx)

            # Getting FK Entity Subnames List
            if currentTargetEntity != '':
                selectorFkSubnameList = self.GetDataAsList('''
                    select
                        t.target_entity_subname
                    from stage_table t
                        join stage_db d on d.stage_db_id = t.stage_db_id
                        join project p on p.project_id = d.project_id
                    where p.project_id = (select d.project_id from stage_table t join stage_db d on d.stage_db_id = t.stage_db_id where t.stage_table_id = {parent_id})
                        and t.target_entity_name = '{currentTargetEntity}'
                    order by 1'''.format(parent_id = str(self.grid.treeItemData['parent_id']), \
                        currentTargetEntity = currentTargetEntity))
            else:
                selectorFkSubnameList = ['']

            if len(selectorFkSubnameList) == 0 or selectorFkSubnameList[0] != '':
                selectorFkSubnameList.insert(0, '')

            # Getting FK Entity Attributes List
            if currentTargetEntity != '':
                selectorFkAttributeList = self.GetDataAsList('''
                    select
                        c.target_attribute_name
                    from stage_column c
                        join stage_table t on t.stage_table_id = c.stage_table_id
                        join stage_db d on d.stage_db_id = t.stage_db_id
                        join project p on p.project_id = d.project_id
                    where p.project_id = (select d.project_id from stage_table t join stage_db d on d.stage_db_id = t.stage_db_id where t.stage_table_id = {parent_id})
                        and t.target_entity_name = '{currentTargetEntity}'
                        and t.target_entity_subname = '{currentTargetEntitySubname}'
                    order by c.target_ordinal_pos'''.format(parent_id = str(self.grid.treeItemData['parent_id']), \
                        currentTargetEntity = currentTargetEntity, currentTargetEntitySubname = currentTargetEntitySubname))
            else:
                selectorFkAttributeList = ['']

            if len(selectorFkAttributeList) == 0 or selectorFkAttributeList[0] != '':
                selectorFkAttributeList.insert(0, '')

            for colIdx in range(self.grid.GetNumberCols()):
                currentColLabel = self.grid.GetColLabelValue(colIdx)

                if (colIdx == 1) \
                        and ((currentColLabel == 'Project Id') or (currentColLabel == 'Stage Db Id') or (currentColLabel == 'Stage Table Id')) \
                        and (self.grid.GetCellValue(rowIdx, colIdx) == ''):
                    self.grid.SetCellValue(rowIdx, colIdx, str(self.grid.treeItemData['parent_id']))

                if currentColLabel == 'Fk Entity Name':
                    self.grid.SetCellEditor(rowIdx, colIdx, gridlib.GridCellChoiceEditor(selectorFkEntityList, allowOthers=False))

                if currentColLabel == 'Fk Entity Subname':
                    self.grid.SetCellEditor(rowIdx, colIdx, gridlib.GridCellChoiceEditor(selectorFkSubnameList, allowOthers=False))

                if currentColLabel == 'Fk Entity Attribute':
                    self.grid.SetCellEditor(rowIdx, colIdx, gridlib.GridCellChoiceEditor(selectorFkAttributeList, allowOthers=False))


    def SaveGridChanges(self):
        self.log.WriteText("SaveGridChanges")
        if self.grid.treeItemData != None:
            print self.grid.treeItemData

            dataset = []
            for rowIdx in range(self.grid.GetNumberRows()):
                data_row = []
                for colIdx in range(self.grid.GetNumberCols()):
                    #if colIdx > 0:
                    if colIdx == 0 and self.grid.GetCellValue(rowIdx, colIdx) == '':
                        data_row.append(None)
                    else:
                        data_row.append(self.grid.GetCellValue(rowIdx, colIdx))
                dataset.append(data_row)

            self.SaveDataset(self.grid.treeItemData, dataset, True, self.grid.deletedItems)
            self.grid.deletedItems = []
            self.grid.hasUsavedChanges = False


    #---------------------------------------------------------------------------
    # Event handlers

    def OnGridCellChanged(self, event):
        self.grid.hasUsavedChanges = True
        self.UpdateGridSelectors()


    def OnGridRightClick(self, event):
        self.grid.PopupMenu(self.popupMenu)


    def OnTreeSelChanging(self, event): # On Linux, fires twice on every change
        self.log.WriteText("OnTreeSelChanging")
        if self.grid.hasUsavedChanges:
            dlg = wx.MessageDialog(self.frame, "There are unsaved changes pending.\nDo you want to save?", "Warning", wx.YES_NO | wx.CANCEL | wx.YES_DEFAULT | wx.ICON_EXCLAMATION)
            result = dlg.ShowModal()
            dlg.Destroy()

            if result == wx.ID_YES:
                self.SaveGridChanges()
                event.Skip()

            elif result == wx.ID_NO:
                self.grid.deletedItems = []
                self.grid.hasUsavedChanges = False
                event.Skip()

            else:
                event.Veto()


    def OnTreeSelChanged(self, event):
        item = event.GetItem()
        if item:
            self.log.WriteText("OnTreeSelChanged: %s\n" % self.tree.GetItemText(item))
            #items = self.tree.GetSelections()
            #print map(self.tree.GetItemText, items)

            self.grid.treeItemData = self.tree.GetPyData(item)
            self.RefreshGrid()
        event.Skip()


    def OnButtonAddItem(self, event):
        if self.grid.AppendRows(1):
            self.UpdateGridEditors()
            self.UpdateGridSelectors()
            self.grid.hasUsavedChanges = True


    def OnButtonImportItem(self, event):
        # TODO: Import items from Postgres
        table = self.grid.treeItemData['table']
        parent_id = str(self.grid.treeItemData['parent_id'])
        currentTableName = []
        currentTableNameStr = ''
        connString = []

        if table == 'stage_column':
            currentTableName = self.GetDataAsList("""
                select
                    t.schema_name || '.' || t.table_name as table_name
                from stage_table t
                where t.stage_table_id = {0}""".format(parent_id))

            connString = self.GetDataAsList("""
                select
                    'host=''' || d.host || ''' port=''' || d.port || ''' dbname=''' || d.database || ''' user=''' || d.user || ''' password=''' || d.password || '''' as conn_string
                from stage_db d
                    join stage_table t on t.stage_db_id = d.stage_db_id
                where t.stage_table_id = {0}""".format(parent_id))

        elif table == 'stage_table':
            connString = self.GetDataAsList("""
                select
                    'host=''' || d.host || ''' port=''' || d.port || ''' dbname=''' || d.database || ''' user=''' || d.user || ''' password=''' || d.password || '''' as conn_string
                from stage_db d
                where d.stage_db_id = {0}""".format(parent_id))

        else:
            return

        if len(connString) > 0 and connString[0] != '':
            if len(currentTableName) > 0:
                currentTableNameStr = currentTableName[0]
            dlg = ImportDialog(connString[0], currentTableNameStr)

            result = dlg.ShowModal()
            if result == wx.ID_OK:
                print 'Selected items:'
                print dlg.resultDataset

                if table == 'stage_column':
                    for row in dlg.resultDataset:
                        resultSchemaName = str(row[0]).split('.')[0]
                        resultTableName = str(row[0]).split('.')[1]
                        resultColumnName = str(row[1])
                        resultColumnType = str(row[2])
                        resultColumnPos = str(row[3] * 10)

                        if resultColumnType.lower() == 'bpchar':
                            resultColumnType = 'char'

                        with sqlite3.connect(self.db_filename) as conn:
                            #insert columns
                            print """
                                insert into stage_column (stage_table_id, column_name, column_type, target_attribute_name, target_attribute_type, target_ordinal_pos)
                                select {0}, '{1}', '{2}', '{3}', '{4}', {5}
                                """.format(parent_id, resultColumnName.lower(), resultColumnType.lower(), resultColumnName.lower(), resultColumnType.lower(), resultColumnPos)

                            conn.execute("""
                                insert into stage_column (stage_table_id, column_name, column_type, target_attribute_name, target_attribute_type, target_ordinal_pos)
                                select {0}, '{1}', '{2}', '{3}', '{4}', {5}
                                """.format(parent_id, resultColumnName.lower(), resultColumnType.lower(), resultColumnName.lower(), resultColumnType.lower(), resultColumnPos)
                            )

                            conn.commit()

                elif table == 'stage_table':
                    oldSchemaTableName = ''
                    for row in dlg.resultDataset:
                        resultSchemaName = str(row[0]).split('.')[0]
                        resultTableName = str(row[0]).split('.')[1]
                        resultColumnName = str(row[1])
                        resultColumnType = str(row[2])
                        resultColumnPos = str(row[3] * 10)

                        if resultColumnType.lower() == 'bpchar':
                            resultColumnType = 'char'

                        with sqlite3.connect(self.db_filename) as conn:
                            if oldSchemaTableName != str(row[0]):
                                #insert table
                                print """
                                    insert into stage_table (stage_db_id, schema_name, table_name, target_entity_name, target_entity_subname, is_track_changes, is_track_deleted, is_keep_history)
                                    values ({0}, '{1}', '{2}', '{3}', '{4}', '{5}', '{6}', '{7}')
                                    """.format(parent_id, resultSchemaName.lower(), resultTableName.lower(), 'dim_' + resultTableName.lower(), 'main', 1, 0, 1)

                                conn.execute("""
                                    insert into stage_table (stage_db_id, schema_name, table_name, target_entity_name, target_entity_subname, is_track_changes, is_track_deleted, is_keep_history)
                                    values ({0}, '{1}', '{2}', '{3}', '{4}', '{5}', '{6}', '{7}')
                                    """.format(parent_id, resultSchemaName.lower(), resultTableName.lower(), 'dim_' + resultTableName.lower(), 'main', 1, 0, 1)
                                )

                                oldSchemaTableName = str(row[0])

                            #insert columns
                            print """
                                insert into stage_column (stage_table_id, column_name, column_type, target_attribute_name, target_attribute_type, target_ordinal_pos)
                                select max(stage_table_id) as stage_table_id, '{0}', '{1}', '{2}', '{3}', {4} from stage_table
                                """.format(resultColumnName.lower(), resultColumnType.lower(), resultColumnName.lower(), resultColumnType.lower(), resultColumnPos)

                            conn.execute("""
                                insert into stage_column (stage_table_id, column_name, column_type, target_attribute_name, target_attribute_type, target_ordinal_pos)
                                select max(stage_table_id) as stage_table_id, '{0}', '{1}', '{2}', '{3}', {4} from stage_table
                                """.format(resultColumnName.lower(), resultColumnType.lower(), resultColumnName.lower(), resultColumnType.lower(), resultColumnPos)
                            )

                            conn.commit()

                self.RefreshTree()

            dlg.Destroy()

    def OnButtonDeleteItem(self, event):
        self.log.WriteText("OnButtonDeleteItem")
        if self.grid.GetNumberRows() == 0:
            return

        #print self.grid.GetNumberRows()
        currentRow = self.grid.GetGridCursorRow()
        currentID = self.grid.GetCellValue(currentRow, 0)
        print currentID

        dlg = wx.MessageDialog(self.frame, "Are you sure you want to delete selected record?", "Warning", wx.YES_NO | wx.YES_DEFAULT | wx.ICON_EXCLAMATION)
        result = dlg.ShowModal()
        dlg.Destroy()

        if result == wx.ID_YES:
            if currentID != '':
                self.grid.deletedItems.append(currentID)
            self.grid.DeleteRows(currentRow, 1)
            self.grid.hasUsavedChanges = True


    def OnButtonSaveChanges(self, event):
        self.SaveGridChanges()


    def OnButtonSaveAndRefresh(self, event):
        self.SaveGridChanges()
        self.RefreshTree()


    def OnMenuAbout(self, event):
        self.log.WriteText("Clicked About")
        dlg = wx.MessageDialog(self.frame, "A sample program\nin wxPython", "About", wx.OK | wx.ICON_INFORMATION)
        dlg.ShowModal()
        dlg.Destroy()


    def OnMenuRefresh(self, event):
        self.log.WriteText("Clicked Refresh")
        self.RefreshTree()


    def OnMenuGenerateDDL(self, event):
        self.log.WriteText("OnMenuGenerateDDL")
        table = self.grid.treeItemData['table']
        parent_id = str(self.grid.treeItemData['parent_id'])
        if (table != 'stage_column'):
            dlg = wx.MessageDialog(self.frame, "Please select a table in a tree to generate the DDL code for it", "Error", wx.OK | wx.ICON_ERROR)
            dlg.ShowModal()
            dlg.Destroy()
            return

        if self.grid.hasUsavedChanges:
            dlg = wx.MessageDialog(self.frame, "There are unsaved changes pending.\nDo you want to save?", "Warning", wx.YES_NO | wx.CANCEL | wx.YES_DEFAULT | wx.ICON_EXCLAMATION)
            result = dlg.ShowModal()
            dlg.Destroy()

            if result == wx.ID_YES:
                self.SaveGridChanges()

        self.GenerateETL(parent_id, True)


    def OnMenuGenerateETL(self, event):
        self.log.WriteText("OnMenuGenerateETL")
        table = self.grid.treeItemData['table']
        parent_id = str(self.grid.treeItemData['parent_id'])
        if (table != 'stage_column'):
            dlg = wx.MessageDialog(self.frame, "Please select a table in a tree to generate the ETL code for it", "Error", wx.OK | wx.ICON_ERROR)
            dlg.ShowModal()
            dlg.Destroy()
            return

        if self.grid.hasUsavedChanges:
            dlg = wx.MessageDialog(self.frame, "There are unsaved changes pending.\nDo you want to save?", "Warning", wx.YES_NO | wx.CANCEL | wx.YES_DEFAULT | wx.ICON_EXCLAMATION)
            result = dlg.ShowModal()
            dlg.Destroy()

            if result == wx.ID_YES:
                self.SaveGridChanges()

        self.GenerateETL(parent_id, False)


    def OnMenuExit(self, event):
        self.log.WriteText("OnMenuExit")
        self.frame.Close(True)


    def OnFrameClose(self, event):
        self.log.WriteText("OnFrameClose")
        if self.grid.hasUsavedChanges:
            dlg = wx.MessageDialog(self.frame, "There are unsaved changes pending.\nDo you want to save?", "Warning", wx.YES_NO | wx.CANCEL | wx.YES_DEFAULT | wx.ICON_EXCLAMATION)
            result = dlg.ShowModal()
            dlg.Destroy()

            if result == wx.ID_YES:
                self.SaveGridChanges()
                self.frame.Destroy()

            elif result == wx.ID_NO:
                self.grid.deletedItems = []
                self.grid.hasUsavedChanges = False
                self.frame.Destroy()
            else:
                self.log.WriteText("Staying...")
        else:
            self.frame.Destroy()


    def GenerateETL(self, stage_table_id, only_ddl):
        self.log.WriteText('GenerateETL')
        with sqlite3.connect(self.db_filename) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("""
select
    coalesce(d.staging_schema, '') as staging_schema,
    coalesce(d.is_delete_temp_tables, 0) as is_delete_temp_tables,
    coalesce(d.driver, '') as driver,
    coalesce(t.schema_name, '') as schema_name,
    coalesce(t.table_name, '') as table_name,
    coalesce(t.table_expression, '') as table_expression,
    coalesce(t.target_entity_schema, '') as target_entity_schema,
    coalesce(t.target_entity_name, '') as target_entity_name,
    coalesce(t.target_entity_subname, '') as target_entity_subname,
    coalesce(t.target_entity_tablespace, '') as target_entity_tablespace,
    coalesce(t.is_track_changes, 0) as is_track_changes,
    coalesce(t.is_track_deleted, 0) as is_track_deleted,
    coalesce(t.is_keep_history, 0) as is_keep_history,
    coalesce(t.is_truncate_stage, 0) as is_truncate_stage,
    coalesce(t.is_rebuild_indexes, 0) as is_rebuild_indexes,
    case
        when t.target_entity_subname != ''
            then coalesce(t.target_entity_name, '') || '_' || coalesce(t.target_entity_subname, '')
        else coalesce(t.target_entity_name, '')
    end as target_entity_full_name,
    coalesce(c.column_name, '') as column_name,
    coalesce(c.column_expression, '') as column_expression,
    case
        when c.is_unix_timestamp = 1
            -- case when type_long = 0 then NULL else timestamp 'epoch' + type_long * interval '1 second' at time zone 'UTC' end
            then 'decode(' || coalesce(c.column_name, '') || ', 0, NULL, timestamp ''epoch'' + ' || coalesce(c.column_name, '') || ' * interval ''1 second'' at time zone ''UTC'') as ' || coalesce(c.column_name, '')
        else
            case
                when c.column_expression != ''
                    then coalesce(c.column_expression, '') || ' as ' || coalesce(c.column_name, '')
                else coalesce(c.column_name, '')
            end
    end as column_value_decoded,
    case
        when (lower(c.column_type) in ('date','timestamp','datetime')) or (c.is_unix_timestamp = 1)
            then 'to_char(' || coalesce(c.column_name, '') || ', ''YYYYMMDD'') || '''''
        else coalesce(c.column_name, '') || ' || '''''
    end as column_value_for_bk,
    case
        when lower(c.column_type) = 'date'
            then 'coalesce(to_char(' || coalesce(c.column_name, '') || ', ''YYYYMMDD'') || '''', '''')'
        when (lower(c.column_type) in ('timestamp', 'datetime', 'timestamp with time zone', 'timestamp without time zone')) or (c.is_unix_timestamp = 1)
            then 'coalesce(to_char(' || coalesce(c.column_name, '') || ', ''YYYYMMDDHH24MISS'') || '''', '''')'
        else 'coalesce(' || coalesce(c.column_name, '') || ' || '''', '''')'
    end as column_value_as_char,
    coalesce(c.column_type, '') as column_type,
    coalesce(c.is_bk, 0) as is_bk,
    coalesce(c.target_ordinal_pos, 0) as target_ordinal_pos,
    coalesce(c.target_attribute_name, '') as target_attribute_name,
    case
        when c.is_unix_timestamp = 1
            then 'timestamp'
        else coalesce(c.target_attribute_type, '')
    end as target_attribute_type,
    coalesce(t_fk.target_entity_schema, '') as fk_entity_schema,
    coalesce(c.fk_entity_name, '') as fk_entity_name,
    coalesce(c.is_fk_inferred, 0) as is_fk_inferred,
    coalesce(c.fk_entity_subname, '') as fk_entity_subname,
    case
        when c.fk_entity_subname != ''
            then coalesce(c.fk_entity_name, '') || '_' || coalesce(c.fk_entity_subname, '')
        else coalesce(c.fk_entity_name, '')
    end as fk_entity_full_name,
    coalesce(c.fk_entity_attribute, '') as fk_entity_attribute,
    coalesce(c.is_fk_mandatory, 0) as is_fk_mandatory,
    coalesce(c.is_unix_timestamp, 0) as is_unix_timestamp,
    coalesce(c.is_date_updated, 0) as is_date_updated,
    coalesce(c.is_ignore_changes, 0) as is_ignore_changes,
    coalesce(c.is_distkey, 0) as is_distkey,
    coalesce(c.is_sortkey, 0) as is_sortkey,
    coalesce(c.is_ignored, 0) as is_ignored,
    coalesce(c.is_partition_by_date, 0) as is_partition_by_date
from stage_column c
    join stage_table t on t.stage_table_id = c.stage_table_id
    join stage_db d on d.stage_db_id = t.stage_db_id
    left join ( -- Until we have real target entities metadata, getting info from sources, avoiding inconsistencies
        select
            target_entity_name,
            max(target_entity_schema) as target_entity_schema -- Might cause problems for entities in different schemas with the same name!
        from stage_table
        group by target_entity_name
    ) t_fk on t_fk.target_entity_name = c.fk_entity_name
where /*c.is_ignored != 1
    and*/ c.stage_table_id = {stage_table_id}
order by c.target_ordinal_pos, c.stage_column_id
""".format(stage_table_id = stage_table_id))

            # Reading common valuse for all rows

            dataset = cur.fetchall()
            row = dataset[0]
            stagingSchema = row['staging_schema']
            isDeleteTempTables = row['is_delete_temp_tables']
            sqlDriver = row['driver']
            schemaName = row['schema_name']
            tableName = row['table_name']
            tableExpression = row['table_expression']
            targetEntitySchema = row['target_entity_schema']
            targetEntityName = row['target_entity_name']
            targetEntitySubName = row['target_entity_subname']
            targetEntityFullName = row['target_entity_full_name']
            targetEntityTablespace = row['target_entity_tablespace']
            isTrackTableChanges = row['is_track_changes']
            isTrackDeletedRows = row['is_track_deleted']
            isKeepTableHistory = row['is_keep_history']
            isTruncateStage = row['is_truncate_stage']
            isRebuildIndexes = row['is_rebuild_indexes']
            dropTableSection = ""

            # -----------------------------------------------------------------
            # SQL Driver related differences

            if sqlDriver == "postgres":
                currentTimestamp = "current_timestamp"
                DDLMaxVarchar = "varchar"
                DDLAutoIncrementSeq = """drop sequence if exists {targetEntitySchema}.{targetEntityName}_seq;

create sequence {targetEntitySchema}.{targetEntityName}_seq;
""".format(targetEntitySchema = targetEntitySchema, targetEntityName = targetEntityName)
                DDLAutoIncrementColumnType = "default nextval('{targetEntitySchema}.{targetEntityName}_seq')".format(targetEntitySchema = targetEntitySchema, \
                    targetEntityName = targetEntityName)
                DDLDistributionColumnType = "primary key"

            else: #if sqlDriver == "redshift":
                currentTimestamp = "getdate()"
                DDLMaxVarchar = "varchar(max)"
                DDLAutoIncrementSeq = ""
                DDLAutoIncrementColumnType = "identity"
                DDLDistributionColumnType = "distkey"

            if targetEntityTablespace != '' and sqlDriver != "redshift":
                DDLTablespace = " tablespace {targetEntityTablespace}".format(targetEntityTablespace = targetEntityTablespace)
            else:
                DDLTablespace = ""

            # -----------------------------------------------------------------
            # Generating DDL section

            DDLTableEntityKey = """
    entity_key bigint {DDLDistributionColumnType},""".format(DDLDistributionColumnType = DDLDistributionColumnType)

            # For History tables, Redshift can have Distkey, but Postgres can't have PK here, as there will be duplicates
            if sqlDriver == "redshift":
                DDLTableHistEntityKey = """
    entity_key bigint {DDLDistributionColumnType},""".format(DDLDistributionColumnType = DDLDistributionColumnType)
            else:
                DDLTableHistEntityKey = """
    entity_key bigint,"""

            DDLTableColumns = ""

            DDLPKCreate = """alter table {targetEntitySchema}.{targetEntityFullName} add primary key (entity_key);
""".format(targetEntityFullName = targetEntityFullName, targetEntitySchema = targetEntitySchema)

            DDLPKDrop = """alter table {targetEntitySchema}.{targetEntityFullName} drop constraint if exists {targetEntityFullName}_pkey;
""".format(targetEntityFullName = targetEntityFullName, targetEntitySchema = targetEntitySchema)

            DDLFKIndexesDrop = ""

            DDLFKIndexes = ""
            DDLFKIndexesHistory = ""
            DDLFKIndexesStage1 = ""

            DDLPartitionIndexes = ""

            if sqlDriver != "redshift":
                DDLFKIndexesHistory += """create index {targetEntityFullName}_history_entity_key_idx
on {targetEntitySchema}.{targetEntityFullName}_history using btree
(entity_key){DDLTablespace};

create index {targetEntityFullName}_history_batch_date_idx
on {targetEntitySchema}.{targetEntityFullName}_history using btree
(batch_date){DDLTablespace};

create index {targetEntityFullName}_history_batch_date_new_idx
on {targetEntitySchema}.{targetEntityFullName}_history using btree
(batch_date_new){DDLTablespace};

""".format(targetEntityFullName = targetEntityFullName, targetEntitySchema = targetEntitySchema, DDLTablespace = DDLTablespace)

                DDLFKIndexesStage1 += """create index {targetEntityFullName}_stage1_entity_bk_idx
on {stagingSchema}.{targetEntityFullName}_stage1 using btree
(entity_bk){DDLTablespace};

create index {targetEntityFullName}_stage1_row_number_idx
on {stagingSchema}.{targetEntityFullName}_stage1 using btree
(row_number){DDLTablespace};

""".format(targetEntityFullName = targetEntityFullName, stagingSchema = stagingSchema, DDLTablespace = DDLTablespace)

            # Looking for Partitioning flag
            DDLPartitioningColumn = ""
            DDLDropCascade = ""

            if sqlDriver != "redshift":
                for row in dataset:
                    if row['is_ignored'] == 1:
                        continue

                    if (row['target_attribute_type'] == 'date' or row['target_attribute_type'] == 'timestamp') and row['is_partition_by_date'] == 1:
                        DDLPartitioningColumn = row['target_attribute_name']
                        # We'll need to drop all child tables when recreating the main table
                        DDLDropCascade = " cascade"
                        break

            # Scanning through all the columns
            for row in dataset:
                if row['is_ignored'] == 1:
                    continue

                DDLTableColumnKeys = ''
                if (row['is_distkey'] == 1) or (row['is_sortkey'] == 1):

                    if sqlDriver != "redshift": 
                        if (row['fk_entity_name'] == ''): # For Postgres FK columns, we will create indexes for _key columns below. To disable for BK: and (row['is_bk'] != 1) 
                            DDLFKIndexesDrop += """drop index if exists {targetEntitySchema}.{targetEntityFullName}_{target_attribute_name}_idx;
""".format(targetEntityFullName = targetEntityFullName, targetEntitySchema = targetEntitySchema, target_attribute_name = row['target_attribute_name'])

                            DDLFKIndexes += """create index {targetEntityFullName}_{target_attribute_name}_idx
on {targetEntitySchema}.{targetEntityFullName} using btree
({target_attribute_name}){DDLTablespace};

""".format(targetEntityFullName = targetEntityFullName, targetEntitySchema = targetEntitySchema, target_attribute_name = row['target_attribute_name'], \
            DDLTablespace = DDLTablespace)

                            DDLFKIndexesHistory += """create index {targetEntityFullName}_history_{target_attribute_name}_idx
on {targetEntitySchema}.{targetEntityFullName}_history using btree
({target_attribute_name}){DDLTablespace};

""".format(targetEntityFullName = targetEntityFullName, targetEntitySchema = targetEntitySchema, target_attribute_name = row['target_attribute_name'], \
            DDLTablespace = DDLTablespace)

                            DDLPartitionIndexes += """    execute 'create index {targetEntityFullName}_' || current_partition || '_{target_attribute_name}_idx on {targetEntitySchema}.{targetEntityFullName}_' || current_partition || ' using btree ({target_attribute_name}){DDLTablespace};';
""".format(targetEntityFullName = targetEntityFullName, targetEntitySchema = targetEntitySchema, target_attribute_name = row['target_attribute_name'], \
            DDLTablespace = DDLTablespace)

                    else:
                        if (row['is_distkey'] == 1):
                            DDLTableColumnKeys += ' distkey'
                        if (row['is_sortkey'] == 1):
                            DDLTableColumnKeys += ' sortkey'

                if row['fk_entity_name'] != '':
                    DDLTableColumns += """
    {target_attribute_name}_key bigint{DDLTableColumnKeys},
    {target_attribute_name} {target_attribute_type},""".format(target_attribute_name = row['target_attribute_name'], target_attribute_type = row['target_attribute_type'], \
        DDLTableColumnKeys = DDLTableColumnKeys)

                    if sqlDriver != "redshift":
                        DDLFKIndexesDrop += """drop index if exists {targetEntitySchema}.{targetEntityFullName}_{target_attribute_name}_key_idx;
""".format(targetEntityFullName = targetEntityFullName, targetEntitySchema = targetEntitySchema, target_attribute_name = row['target_attribute_name'])

                        DDLFKIndexes += """create index {targetEntityFullName}_{target_attribute_name}_key_idx
on {targetEntitySchema}.{targetEntityFullName} using btree
({target_attribute_name}_key){DDLTablespace};

""".format(targetEntityFullName = targetEntityFullName, targetEntitySchema = targetEntitySchema, target_attribute_name = row['target_attribute_name'], \
        DDLTablespace = DDLTablespace)

                        DDLFKIndexesHistory += """create index {targetEntityFullName}_history_{target_attribute_name}_key_idx
on {targetEntitySchema}.{targetEntityFullName}_history using btree
({target_attribute_name}_key){DDLTablespace};

""".format(targetEntityFullName = targetEntityFullName, targetEntitySchema = targetEntitySchema, target_attribute_name = row['target_attribute_name'], \
        DDLTablespace = DDLTablespace)

                        DDLFKIndexesStage1 += """create index {targetEntityFullName}_stage1_{column_name}_{fk_entity_name}_bk_idx
on {stagingSchema}.{targetEntityFullName}_stage1 using btree
({column_name}_{fk_entity_name}_bk){DDLTablespace};

""".format(targetEntityFullName = targetEntityFullName, stagingSchema = stagingSchema, column_name = row['column_name'], \
        fk_entity_name = row['fk_entity_name'], DDLTablespace = DDLTablespace)

                        DDLPartitionIndexes += """    execute 'create index {targetEntityFullName}_' || current_partition || '_{target_attribute_name}_key_idx on {targetEntitySchema}.{targetEntityFullName}_' || current_partition || ' using btree ({target_attribute_name}_key){DDLTablespace};';
""".format(targetEntityFullName = targetEntityFullName, targetEntitySchema = targetEntitySchema, target_attribute_name = row['target_attribute_name'], \
            DDLTablespace = DDLTablespace)

                else:
                    DDLTableColumns += """
    {target_attribute_name} {target_attribute_type}{DDLTableColumnKeys},""".format(target_attribute_name = row['target_attribute_name'], \
        target_attribute_type = row['target_attribute_type'], DDLTableColumnKeys = DDLTableColumnKeys)

            DDLTableColumns = DDLTableColumns[:-1]

            PKLookupSection = """
drop table if exists {targetEntitySchema}.{targetEntityName}_pk_lookup;

{DDLAutoIncrementSeq}
create table {targetEntitySchema}.{targetEntityName}_pk_lookup (
    entity_bk {DDLMaxVarchar} not null {DDLDistributionColumnType},
    entity_key bigint not null {DDLAutoIncrementColumnType}
){DDLTablespace};
""".format(targetEntitySchema = targetEntitySchema, targetEntityName = targetEntityName, \
        DDLMaxVarchar = DDLMaxVarchar, DDLAutoIncrementColumnType = DDLAutoIncrementColumnType, \
        DDLAutoIncrementSeq = DDLAutoIncrementSeq, DDLDistributionColumnType = DDLDistributionColumnType, \
        DDLTablespace = DDLTablespace)

            # Only generating sequence and pk_lookup table once, for Main entity subname (don't overwrite it with other subnames):
            if targetEntitySubName != 'main':
                PKLookupSection = """
/* Only for Main entity subname
{PKLookupSection}
*/
""".format(PKLookupSection = PKLookupSection)

            # Putting together DDL section
            DDLSection = """
-- Generating DDL for all required tables, only run if the tables don't exist yet
{PKLookupSection}
drop table if exists {targetEntitySchema}.{targetEntityFullName}_batch_info;

create table {targetEntitySchema}.{targetEntityFullName}_batch_info (
    entity_key bigint not null {DDLDistributionColumnType},
    is_inferred smallint not null default 0,
    is_deleted smallint not null default 0,
    hash varchar(128),
    batch_date timestamp not null,
    batch_number bigint not null
){DDLTablespace};

drop table if exists {targetEntitySchema}.{targetEntityFullName}{DDLDropCascade};

create table {targetEntitySchema}.{targetEntityFullName} ({DDLTableEntityKey}{DDLTableColumns}
){DDLTablespace};
""".format(PKLookupSection = PKLookupSection, targetEntitySchema = targetEntitySchema, \
        targetEntityFullName = targetEntityFullName, DDLDistributionColumnType = DDLDistributionColumnType, \
        DDLTableEntityKey = DDLTableEntityKey, DDLTableColumns = DDLTableColumns, DDLTablespace = DDLTablespace, \
        DDLDropCascade = DDLDropCascade)

            # If this table is not partitioned, adding indexes to the main table, otherwise to the child partitions only
            if DDLPartitioningColumn == "":
                DDLSection += """
{DDLFKIndexes}""".format(DDLFKIndexes = DDLFKIndexes)

            if isKeepTableHistory == 1:
                DDLSection += """drop table if exists {targetEntitySchema}.{targetEntityFullName}_history;

create table {targetEntitySchema}.{targetEntityFullName}_history (
    -- History part
    is_inferred smallint default 0,
    is_deleted smallint not null default 0,
    hash varchar(128),
    batch_date timestamp,
    batch_number bigint,
    batch_date_new timestamp,
    batch_number_new bigint,
    -- Main part {DDLTableHistEntityKey}{DDLTableColumns}
){DDLTablespace};

{DDLFKIndexesHistory}""".format(targetEntitySchema = targetEntitySchema, targetEntityFullName = targetEntityFullName, \
        DDLTableHistEntityKey = DDLTableHistEntityKey, DDLTableColumns = DDLTableColumns, DDLTablespace = DDLTablespace, \
        DDLFKIndexesHistory = DDLFKIndexesHistory)

            if DDLPartitioningColumn != "":
                DDLSection += """
drop function if exists {targetEntitySchema}.{targetEntityFullName}_ins_func();

create or replace function {targetEntitySchema}.{targetEntityFullName}_ins_func() returns trigger as
$body$
declare
    current_partition varchar(255);
begin
    current_partition = coalesce(to_char(new.{DDLPartitioningColumn}, 'yyyymm'), 'null');

    -- insert rows to relevant partition if it exists
    execute format('insert into {targetEntitySchema}.{targetEntityFullName}_' || current_partition || ' values($1.*)') using new;

    -- finish execution
    return null;

-- if the table doesn't exist yet, creating it
exception when undefined_table then
    if new.{DDLPartitioningColumn} is not null then
        execute 'create table {targetEntitySchema}.{targetEntityFullName}_' || current_partition || ' (check ({DDLPartitioningColumn} >= ' || quote_literal(to_char(date_trunc('month', new.{DDLPartitioningColumn}), 'yyyy-mm-dd')) || ' and {DDLPartitioningColumn} < ' || quote_literal(to_char(date_trunc('month', new.{DDLPartitioningColumn}) + interval '1 month', 'yyyy-mm-dd')) || '), primary key (entity_key)) inherits ({targetEntitySchema}.{targetEntityFullName}){DDLTablespace};';
    else
        execute 'create table {targetEntitySchema}.{targetEntityFullName}_' || current_partition || ' (check ({DDLPartitioningColumn} is null), primary key (entity_key)) inherits ({targetEntitySchema}.{targetEntityFullName}){DDLTablespace};';
    end if;

    -- create required local indexes, if any, for each partition (child table)
{DDLPartitionIndexes}
    -- insert first row to the created parition
    execute format('insert into {targetEntitySchema}.{targetEntityFullName}_' || current_partition || ' values($1.*)') using new;

    -- finish execution
    return null;
end;
$body$
language plpgsql;

drop trigger if exists {targetEntityFullName}_ins_trigger on {targetEntitySchema}.{targetEntityFullName};

create trigger {targetEntityFullName}_ins_trigger
before insert
on {targetEntitySchema}.{targetEntityFullName}
for each row
execute procedure {targetEntitySchema}.{targetEntityFullName}_ins_func();
""".format(targetEntityFullName = targetEntityFullName, targetEntitySchema = targetEntitySchema, DDLTablespace = DDLTablespace, \
            DDLPartitioningColumn = DDLPartitioningColumn, DDLPartitionIndexes = DDLPartitionIndexes)


            # -----------------------------------------------------------------
            # Saving a DDL file

            if only_ddl == True:
                saveFileDialog = wx.FileDialog(self.frame, "Save SQL file", "", targetEntitySchema + "." + targetEntityFullName + "_ddl.sql",
                                               "SQL files (*.sql)|*.sql", wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)

                if saveFileDialog.ShowModal() == wx.ID_CANCEL:
                    return     # the user changed idea...

                with open(saveFileDialog.GetPath(), 'w') as f:
                    f.write(DDLSection)

                return


            # -----------------------------------------------------------------
            # Starting code generation

            fullScriptETL = """
-- ETL code for loading {schemaName}.{tableName} to {targetEntitySchema}.{targetEntityFullName}

drop table if exists {stagingSchema}.{targetEntityFullName}_batch; -- Won't drop to avoid unnoticed collisions

create table {stagingSchema}.{targetEntityFullName}_batch{DDLTablespace} as
select
    {currentTimestamp} as batch_date,
    #JOB_ID# as batch_number
;

""".format(stagingSchema = stagingSchema, schemaName = schemaName, tableName = tableName, \
        targetEntitySchema = targetEntitySchema, targetEntityFullName = targetEntityFullName, \
        currentTimestamp = currentTimestamp, DDLTablespace = DDLTablespace, DDLSection = DDLSection)

            dropTableSection += """
drop table if exists {stagingSchema}.{targetEntityFullName}_batch;""".format(stagingSchema = stagingSchema, \
        targetEntityFullName = targetEntityFullName)

            # -----------------------------------------------------------------
            # Generating Stage1 section with all Business Keys

            # Building a sub-sub-query for a source table with all required columns transformations and column expressions
            sourceColumnsLevel1 = ""

            # Building a sub-query with Hash and BK expressions
            sourceColumnsLevel2 = ""

            # Building a list of columns to select
            sourceColumnsLevel3 = ""

            # Building the entity's Business Key expression
            sourceColumnsBK = ""

            # Building the Foreign Business Keys column names
            sourceColumnsFKBKNames = ""

            # Building the Foreign Business Keys expressions
            sourceColumnsFKBK = ""

            # Building the source columns hash
            sourceColumnsHash = ""

            # Trying to find the Date Updated column, if any
            sourceColumnDateUpdated = ""

            for row in dataset:
                # Use all (even ignored) columns in first select from source table:
                sourceColumnsLevel1 += """
            {column_value_decoded},""".format(column_value_decoded = row['column_value_decoded'])

                sourceColumnsLevel2 += """
        {column_name},""".format(column_name = row['column_name'])

                # Date Updated can still be used in order by of the Hash, even if is_ignored = true:
                if row['is_date_updated'] == 1:
                    sourceColumnDateUpdated += "{0} desc nulls last, ".format(row['column_name'])

                # Not using ignored columns for anything else:
                if row['is_ignored'] == 1:
                    continue

                sourceColumnsLevel3 += """
    {column_name},""".format(column_name = row['column_name'])

                if row['is_ignore_changes'] != 1:
                    sourceColumnsHash += """
            {column_value_as_char} ||""".format(column_value_as_char = row['column_value_as_char'])

                if row['is_bk'] == 1:
                    sourceColumnsBK += "{column_value_as_char} || '^' || ".format(column_value_as_char = row['column_value_as_char'])

                if row['fk_entity_name'] != '':
                    sourceColumnsFKBKNames += """
    {column_name}_{fk_entity_name}_bk,""".format(column_name = row['column_name'], fk_entity_name = row['fk_entity_name'])

                    if row['is_fk_mandatory'] == 1:
                        sourceColumnsFKBK += """
        coalesce({column_value_for_bk}, '') as {column_name}_{fk_entity_name}_bk,""".format(column_value_for_bk = row['column_value_for_bk'], \
                            column_name = row['column_name'], fk_entity_name = row['fk_entity_name'])
                    else:
                        sourceColumnsFKBK += """
        {column_value_for_bk} as {column_name}_{fk_entity_name}_bk,""".format(column_value_for_bk = row['column_value_for_bk'], \
                            column_name = row['column_name'], fk_entity_name = row['fk_entity_name'])

            sourceColumnsLevel1 = sourceColumnsLevel1[:-1] # Removing the last comma from Level1 select
            sourceColumnsBK = sourceColumnsBK[:-11] # Removing the last concatenation

            if isTrackTableChanges == 1:
                sourceColumnsHash = """
        md5( {sourceColumnsHash}
        )""".format(sourceColumnsHash = sourceColumnsHash[:-3]) # Removing the ||
            else:
                sourceColumnsHash = """
        cast(null as varchar)"""

            # Building Level1 of the source table select, depending if the source table is an expression or not:
            if tableExpression != '':
                sourceTableSelect = """
        select {sourceColumnsLevel1}
        from (
            {tableExpression}
        ) s3
    """.format(sourceColumnsLevel1 = sourceColumnsLevel1, tableExpression = tableExpression)

            else:
                sourceTableSelect = """
        select {sourceColumnsLevel1}
        from {schemaName}.{tableName}
    """.format(sourceColumnsLevel1 = sourceColumnsLevel1, schemaName = schemaName, tableName = tableName)

            # Wrapping Level1 select with Level2 select, adding BK and Hash calculations:
            sourceTableSelect = """
    select {sourceColumnsLevel2}
        {sourceColumnsBK} as entity_bk, {sourceColumnsFKBK} {sourceColumnsHash} as hash
    from ({sourceTableSelect}) s2
""".format(sourceColumnsLevel2 = sourceColumnsLevel2, sourceTableSelect = sourceTableSelect, \
        sourceColumnsBK = sourceColumnsBK, sourceColumnsFKBK = sourceColumnsFKBK, sourceColumnsHash = sourceColumnsHash)

            # Wrapping resulting Level2 select with Level3 select and the whole Staging table expression
            fullScriptETL += """
drop table if exists {stagingSchema}.{targetEntityFullName}_stage1;

create table {stagingSchema}.{targetEntityFullName}_stage1{DDLTablespace} as
select {sourceColumnsLevel3}
    entity_bk, {sourceColumnsFKBKNames}
    hash,
    row_number() over (partition by entity_bk order by {sourceColumnDateUpdated}hash) as row_number
from ({sourceTableSelect}) s1;

{DDLFKIndexesStage1}""".format(stagingSchema = stagingSchema, targetEntityFullName = targetEntityFullName, sourceColumnsLevel3 = sourceColumnsLevel3, \
    sourceColumnsBK = sourceColumnsBK, sourceColumnsFKBKNames = sourceColumnsFKBKNames, sourceColumnsHash = sourceColumnsHash, \
    sourceColumnDateUpdated = sourceColumnDateUpdated, sourceTableSelect = sourceTableSelect, DDLTablespace = DDLTablespace,
    DDLFKIndexesStage1 = DDLFKIndexesStage1)

            dropTableSection += """
drop table if exists {stagingSchema}.{targetEntityFullName}_stage1;""".format(stagingSchema = stagingSchema, \
    targetEntityFullName = targetEntityFullName)

            # -----------------------------------------------------------------
            # Generating Inferred sections for each row with FK

            inferredEntitiesSection = ""

            for row in dataset:
                if row['is_ignored'] == 1:
                    continue

                if row['fk_entity_attribute'] != '':
                    targetAttributeSelect = """,
    max(s1.{column_name}) as {fk_entity_attribute}""".format(column_name = row['column_name'], fk_entity_attribute = row['fk_entity_attribute'])
                    targetAttributeInsertColumn = """,
    {fk_entity_attribute}""".format(fk_entity_attribute = row['fk_entity_attribute'])
                    targetAttributeInsertSelect = """,
    i.{fk_entity_attribute}""".format(fk_entity_attribute = row['fk_entity_attribute'])

                else:
                    targetAttributeSelect = ""
                    targetAttributeInsertColumn = ""
                    targetAttributeInsertSelect = ""

                if row['fk_entity_full_name'] != '' and row['is_fk_inferred'] == 1:
                    if sqlDriver != "redshift":
                        DDLIndexInferredStage = """create index {fk_entity_full_name}_inferred_#JOB_ID#_entity_bk_idx
on {stagingSchema}.{fk_entity_full_name}_inferred_#JOB_ID# using btree
(entity_bk){DDLTablespace};

""".format(fk_entity_full_name = row['fk_entity_full_name'], stagingSchema = stagingSchema, DDLTablespace = DDLTablespace)
                    else:
                        DDLIndexInferredStage = ""

                    inferredEntitiesSection += """
-- Inferred entity: {fk_entity_full_name}

begin;
lock table {fk_entity_schema}.{fk_entity_name}_pk_lookup in exclusive mode;
lock table {fk_entity_schema}.{fk_entity_full_name}_batch_info in exclusive mode;
lock table {fk_entity_schema}.{fk_entity_full_name} in exclusive mode;

drop table if exists {stagingSchema}.{fk_entity_full_name}_inferred_#JOB_ID#;

create table {stagingSchema}.{fk_entity_full_name}_inferred_#JOB_ID#{DDLTablespace} as
select
    p.entity_key, -- Not null if entity exists, but was not loaded to this entity suffix before
    s1.{column_name}_{fk_entity_name}_bk as entity_bk {targetAttributeSelect}
from {stagingSchema}.{targetEntityFullName}_stage1 s1
    left join {fk_entity_schema}.{fk_entity_name}_pk_lookup p
        on p.entity_bk = s1.{column_name}_{fk_entity_name}_bk
    left join {fk_entity_schema}.{fk_entity_full_name}_batch_info bi
        on bi.entity_key = p.entity_key
where s1.row_number = 1
    and s1.{column_name}_{fk_entity_name}_bk is not null -- Ignoring NULL FKs
    and bi.entity_key is null -- Entity either completely new or was not loaded to this entity suffix before
group by 1,2
;

{DDLIndexInferredStage}
insert into {fk_entity_schema}.{fk_entity_name}_pk_lookup (entity_bk)
select i.entity_bk
from {stagingSchema}.{fk_entity_full_name}_inferred_#JOB_ID# i
where i.entity_key is null -- Entity is completely new
;

-- Analyze takes too much time, disabled for inferred entities
-- analyze {fk_entity_schema}.{fk_entity_name}_pk_lookup;

insert into {fk_entity_schema}.{fk_entity_full_name}_batch_info (
    entity_key,
    is_inferred,
    is_deleted,
    hash,
    batch_date,
    batch_number
)
select
    p.entity_key, -- Using just generated or already exising key which was not loaded to this entity suffix before
    1 as is_inferred,
    0 as is_deleted,
    '{targetEntitySchema}.{targetEntityFullName}' as hash,
    b.batch_date,
    b.batch_number
from {stagingSchema}.{fk_entity_full_name}_inferred_#JOB_ID# i
    left join {fk_entity_schema}.{fk_entity_name}_pk_lookup p
        on p.entity_bk = i.entity_bk
    cross join {stagingSchema}.{targetEntityFullName}_batch b
;

-- Analyze takes too much time, disabled for inferred entities
-- analyze {fk_entity_schema}.{fk_entity_full_name}_batch_info;

insert into {fk_entity_schema}.{fk_entity_full_name} (
    entity_key {targetAttributeInsertColumn}
)
select
    p.entity_key {targetAttributeInsertSelect}
from {stagingSchema}.{fk_entity_full_name}_inferred_#JOB_ID# i
    join {fk_entity_schema}.{fk_entity_name}_pk_lookup p
        on p.entity_bk = i.entity_bk
;

-- Analyze takes too much time, disabled for inferred entities
-- analyze {fk_entity_schema}.{fk_entity_full_name};

commit;
""".format(stagingSchema = stagingSchema, schemaName = schemaName, tableName = tableName, column_name = row['column_name'], \
    fk_entity_schema = row['fk_entity_schema'], fk_entity_name = row['fk_entity_name'], fk_entity_full_name = row['fk_entity_full_name'], \
    targetEntitySchema = targetEntitySchema, targetEntityFullName = targetEntityFullName, targetAttributeSelect = targetAttributeSelect, \
    targetAttributeInsertColumn = targetAttributeInsertColumn, targetAttributeInsertSelect = targetAttributeInsertSelect, \
    DDLTablespace = DDLTablespace, DDLIndexInferredStage = DDLIndexInferredStage)

                    dropTableSection += """
drop table if exists {stagingSchema}.{fk_entity_full_name}_inferred_#JOB_ID#;""".format(stagingSchema = stagingSchema, \
    fk_entity_full_name = row['fk_entity_full_name'])

            if inferredEntitiesSection != "":
                fullScriptETL += """
-- Inferred entities loading start
{inferredEntitiesSection}
-- Inferred entities loading end

""".format(inferredEntitiesSection = inferredEntitiesSection)

            # -----------------------------------------------------------------
            # Generating Lookup section

            if sqlDriver != "redshift":
                DDLIndexLookupStage = """create index {targetEntityFullName}_pk_batch_info_stage_entity_bk_idx
on {stagingSchema}.{targetEntityFullName}_pk_batch_info_stage using btree
(entity_bk){DDLTablespace};

""".format(targetEntityFullName = targetEntityFullName, stagingSchema = stagingSchema, DDLTablespace = DDLTablespace)
            else:
                DDLIndexLookupStage = ""

            if isTrackDeletedRows == 1:
                PKLookupJoinType = "full outer join"
            else:
                PKLookupJoinType = "left join"

            lookupSection = """
-- Generating the list of new/updated/deleted entities

begin;
lock table {targetEntitySchema}.{targetEntityName}_pk_lookup in exclusive mode;
lock table {targetEntitySchema}.{targetEntityFullName}_batch_info in exclusive mode;
lock table {targetEntitySchema}.{targetEntityFullName} in exclusive mode;

drop table if exists {stagingSchema}.{targetEntityFullName}_pk_batch_info_stage;

create table {stagingSchema}.{targetEntityFullName}_pk_batch_info_stage{DDLTablespace} as
select
    s1.entity_bk,
    p.entity_key, -- Will be null for new entities
    bi.is_inferred as is_inferred_old,
    0 as is_inferred,
    bi.is_deleted as is_deleted_old,
    case when s1.entity_bk is null then 1 else 0 end as is_deleted,
    bi.hash as hash_old, -- Saving old hash and batch information for updated entities
    s1.hash,
    bi.batch_date as batch_date_old,
    bi.batch_number as batch_number_old,
    b.batch_date,
    b.batch_number
from {stagingSchema}.{targetEntityFullName}_stage1 s1
    {PKLookupJoinType} {targetEntitySchema}.{targetEntityName}_pk_lookup p
        on p.entity_bk = s1.entity_bk
    left join {targetEntitySchema}.{targetEntityFullName}_batch_info bi
        on bi.entity_key = p.entity_key
    cross join {stagingSchema}.{targetEntityFullName}_batch b
where (s1.entity_bk is not null
        and s1.row_number = 1
        and ((p.entity_key is null)     -- New entity
            or (bi.entity_key is null)  -- Entity key exists, but not in this entity subname (sattelite)
            or (bi.is_inferred = 1)     -- This entity subname was loaded, but as inferred
            or (bi.is_deleted = 1)      -- This entity subname was deleted before, but arrived again now
            or (coalesce(bi.hash, '') != s1.hash)) -- This entity subname was loaded, but the attributes changed (or we didn't track history before)
    )
    or (s1.entity_bk is null            -- Entity is missing from loaded full snapshot data (deleted)
        and bi.is_deleted = 0           -- Entity is not deleted before
        and bi.is_inferred = 0          -- We will not delete inferred records, because they were never actually loaded
    )
;

{DDLIndexLookupStage}
-- Inserting new entities to PK Lookup, generating keys

insert into {targetEntitySchema}.{targetEntityName}_pk_lookup (entity_bk)
select ps.entity_bk
from {stagingSchema}.{targetEntityFullName}_pk_batch_info_stage ps
where ps.entity_key is null -- Only new entities
;

analyze {targetEntitySchema}.{targetEntityName}_pk_lookup;

-- Inserting Batch information and Hash for new entities

insert into {targetEntitySchema}.{targetEntityFullName}_batch_info (
    entity_key,
    is_inferred,
    is_deleted,
    hash,
    batch_date,
    batch_number
)
select
    p.entity_key,
    ps.is_inferred,
    ps.is_deleted,
    ps.hash,
    ps.batch_date,
    ps.batch_number
from {stagingSchema}.{targetEntityFullName}_pk_batch_info_stage ps
    join {targetEntitySchema}.{targetEntityName}_pk_lookup p
        on p.entity_bk = ps.entity_bk
where ps.batch_number_old is null -- This entity subname wasn't loaded before
;

-- Updating Batch information and Hash for changed entities

update {targetEntitySchema}.{targetEntityFullName}_batch_info
set
    is_inferred = ps.is_inferred,
    is_deleted = ps.is_deleted,
    hash = ps.hash,
    batch_date = ps.batch_date,
    batch_number = ps.batch_number
from {stagingSchema}.{targetEntityFullName}_pk_batch_info_stage ps
where ps.entity_key = {targetEntitySchema}.{targetEntityFullName}_batch_info.entity_key
    and ps.batch_number_old is not null -- This entity subname was already loaded
;

analyze {targetEntitySchema}.{targetEntityFullName}_batch_info;
""".format(stagingSchema = stagingSchema, targetEntityName = targetEntityName, targetEntityFullName = targetEntityFullName, \
        targetEntitySchema = targetEntitySchema, DDLTablespace = DDLTablespace, DDLIndexLookupStage = DDLIndexLookupStage, \
        PKLookupJoinType = PKLookupJoinType)

            dropTableSection += """
drop table if exists {stagingSchema}.{targetEntityFullName}_pk_batch_info_stage;""".format(stagingSchema = stagingSchema, \
    targetEntityFullName = targetEntityFullName)

            fullScriptETL += lookupSection

            # -----------------------------------------------------------------
            # Generating Stage2 section

            targetTableColumns = """
    entity_key,"""
            stage2SelectColumns = ""
            stage2SelectJoins = ""

            for row in dataset:
                if row['is_ignored'] == 1:
                    continue

                if row['fk_entity_name'] != '':
                    targetTableColumns += """
    {target_attribute_name}_key,
    {target_attribute_name},""".format(target_attribute_name = row['target_attribute_name'])

                    stage2SelectColumns += """
    p_{column_name}_{fk_entity_name}.entity_key as {target_attribute_name}_key,
    s1.{column_name} as {target_attribute_name},""".format(column_name = row['column_name'], fk_entity_name = row['fk_entity_name'], \
            target_attribute_name = row['target_attribute_name'])

                    stage2SelectJoins += """
    left join {fk_entity_schema}.{fk_entity_name}_pk_lookup as p_{column_name}_{fk_entity_name}
        on p_{column_name}_{fk_entity_name}.entity_bk = s1.{column_name}_{fk_entity_name}_bk""".format(fk_entity_schema = row['fk_entity_schema'], \
            fk_entity_name = row['fk_entity_name'], column_name = row['column_name'])

                else:
                    targetTableColumns += """
    {target_attribute_name},""".format(target_attribute_name = row['target_attribute_name'])

                    stage2SelectColumns += """
    s1.{column_name} as {target_attribute_name},""".format(column_name = row['column_name'], target_attribute_name = row['target_attribute_name'])

            targetTableColumns = targetTableColumns[:-1]

            stage2SelectColumns = stage2SelectColumns[:-1]

            # Putting together Stage2 table
            stage2Section = """
-- Generating Stage2 table, similar to target table by structure

drop table if exists {stagingSchema}.{targetEntityFullName}_stage2;

create table {stagingSchema}.{targetEntityFullName}_stage2{DDLTablespace} as
select
    p.entity_key, {stage2SelectColumns}
from {stagingSchema}.{targetEntityFullName}_pk_batch_info_stage as ps    -- Only new, inferred or updated entities
    join {stagingSchema}.{targetEntityFullName}_stage1 as s1    -- Taking other columns from the source table
        on s1.entity_bk = ps.entity_bk
    join {targetEntitySchema}.{targetEntityName}_pk_lookup as p    -- Using just generated or already exising keys
        on p.entity_bk = ps.entity_bk {stage2SelectJoins}
where s1.entity_bk is not null -- Entity not deleted
    and s1.row_number = 1
;
""".format(stagingSchema = stagingSchema, targetEntityName = targetEntityName, targetEntityFullName = targetEntityFullName, \
        targetEntitySchema = targetEntitySchema, stage2SelectColumns = stage2SelectColumns, \
        stage2SelectJoins = stage2SelectJoins, DDLTablespace = DDLTablespace)

            dropTableSection += """
drop table if exists {stagingSchema}.{targetEntityFullName}_stage2;""".format(stagingSchema = stagingSchema, \
    targetEntityFullName = targetEntityFullName)

            fullScriptETL += stage2Section

            # -----------------------------------------------------------------
            # Generating History section

            if isKeepTableHistory == 1:
                historySection = """
-- Inserting updated entities to History

insert into {targetEntitySchema}.{targetEntityFullName}_history
select
    ps.is_inferred_old as is_inferred,
    ps.is_deleted_old as is_deleted,
    ps.hash_old as hash,
    ps.batch_date_old as batch_date,
    ps.batch_number_old as batch_number,
    ps.batch_date as batch_date_new,
    ps.batch_number as batch_number_new,
    t.*
from {targetEntitySchema}.{targetEntityFullName} t
    join {stagingSchema}.{targetEntityFullName}_pk_batch_info_stage ps
        on ps.entity_key = t.entity_key
where ps.batch_number_old is not null -- This entity suffix already existed
    -- Not keeping the history, generated by the same Batch (parent IDs coming in the same Batch as child)
    and not (ps.batch_number_old = ps.batch_number and ps.is_inferred_old = 1)
;

analyze {targetEntitySchema}.{targetEntityFullName}_history;
""".format(stagingSchema = stagingSchema, targetEntityFullName = targetEntityFullName, targetEntitySchema = targetEntitySchema)

                fullScriptETL += historySection

            # -----------------------------------------------------------------
            # Generating Updated section (also applies to inferred records)

            updatedSection = """
-- Deleting updated entities from target table

delete from {targetEntitySchema}.{targetEntityFullName}
where entity_key in ( -- or where exists
    select ps.entity_key
    from {stagingSchema}.{targetEntityFullName}_pk_batch_info_stage ps
    where ps.entity_key is not null
        and ps.batch_number_old is not null -- This entity suffix already existed
);
""".format(stagingSchema = stagingSchema, targetEntityFullName = targetEntityFullName, targetEntitySchema = targetEntitySchema)

            fullScriptETL += updatedSection

            # -----------------------------------------------------------------
            # Dropping target table indexes if needed

            if isRebuildIndexes == 1:
                fullScriptETL += """
 -- Droping target table indexes
{DDLPKDrop}
{DDLFKIndexesDrop}""".format(DDLPKDrop = DDLPKDrop, DDLFKIndexesDrop = DDLFKIndexesDrop)
            # -----------------------------------------------------------------
            # Generating target table insert section

            insertTargetSection = """
-- Inserting new, inferred and updated entities to the target table

insert into {targetEntitySchema}.{targetEntityFullName} ( {targetTableColumns}
)
select {targetTableColumns}
from {stagingSchema}.{targetEntityFullName}_stage2
;

analyze {targetEntitySchema}.{targetEntityFullName};

commit;
""".format(stagingSchema = stagingSchema, targetEntityFullName = targetEntityFullName, targetEntitySchema = targetEntitySchema, \
    targetTableColumns = targetTableColumns)

            fullScriptETL += insertTargetSection

            # -----------------------------------------------------------------
            # Recreating target table indexes if needed

            if isRebuildIndexes == 1:
                fullScriptETL += """
 -- Recreating target table indexes
{DDLPKCreate}
{DDLFKIndexes}""".format(DDLPKCreate = DDLPKCreate, DDLFKIndexes = DDLFKIndexes)

            # -----------------------------------------------------------------
            # Generating a drop table statements if needed

            if isDeleteTempTables == 1:
                fullScriptETL += """
-- Dropping temporary staging tables
{dropTableSection}
""".format(dropTableSection = dropTableSection)

            # -----------------------------------------------------------------
            # Truncating source staging table if needed (only for direct tables, not expressions)

            if isTruncateStage == 1 and tableExpression == '':
                fullScriptETL += """
 -- Truncating source staging table
truncate table {schemaName}.{tableName};
""".format(schemaName = schemaName, tableName = tableName)

            # -----------------------------------------------------------------
            # Saving a file

            saveFileDialog = wx.FileDialog(self.frame, "Save SQL file", "", targetEntitySchema + "." + targetEntityFullName + ".sql",
                                           "SQL files (*.sql)|*.sql", wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)

            if saveFileDialog.ShowModal() == wx.ID_CANCEL:
                return     # the user changed idea...

            with open(saveFileDialog.GetPath(), 'w') as f:
                f.write(fullScriptETL)


#---------------------------------------------------------------------------
# Import dialog

class ImportDialog(wx.Dialog):
    # TODO: Return an array of schemas, tables and column selected
    def __init__(self, connString, tableName):
        wx.Dialog.__init__(self, None, title="Import Dialog")

        self.tableName = tableName
        self.resultDataset = []
        self.connected = False

        listboxItems = []

        try:
            self.conn = psycopg2.connect(connString)
            self.connected = True
        except:
            print "Unable to connect to the database."

        if self.connected:
            self.cur = self.conn.cursor()#(cursor_factory=psycopg2.extras.DictCursor)

            if self.tableName != '':
                query = "select column_name from information_schema.columns where table_schema || '.' || table_name = '{}' order by ordinal_position".format(tableName)
            else:
                query = "select table_schema || '.' || table_name as table_name from information_schema.tables order by table_schema, table_name"

            # TODO: If tableName is set, selecting specific columns, otherwise the whole tables
            print query
            try:
                self.cur.execute(query)
            except:
                print "Can't select"

            rows = self.cur.fetchall()

            for row in rows:
                listboxItems.append(row[0])

        self.ListBox = wx.ListBox(self, choices = listboxItems, style = wx.LB_EXTENDED)
        buttonOK = wx.Button(self, wx.ID_OK)
        self.Bind(wx.EVT_BUTTON, self.OnButtonOK, buttonOK)
        buttonCancel = wx.Button(self, wx.ID_CANCEL)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.ListBox, 0, wx.ALL|wx.CENTER, 5)
        sizer.Add(buttonOK, 0, wx.ALL|wx.CENTER, 5)
        sizer.Add(buttonCancel, 0, wx.ALL|wx.CENTER, 5)

        self.SetSizer(sizer)
        self.CentreOnScreen()


    def OnButtonOK(self, event):
        selectedItemsString = ''

        if len(self.ListBox.GetSelections()) > 0:
            for itemIdx in self.ListBox.GetSelections():
                selectedItemsString += "'" + self.ListBox.GetString(itemIdx) + "',"

            selectedItemsString = selectedItemsString[:-1]

            if self.tableName != '':
                where = "where table_schema || '.' || table_name = '{tableName}' and column_name in ({selectedItemsString})".format(tableName = self.tableName, selectedItemsString = selectedItemsString)

            else:
                where = "where table_schema || '.' || table_name in ({selectedItemsString})".format(selectedItemsString = selectedItemsString)

            query = """
                select
                    table_schema || '.' || table_name as table_name,
                    column_name,
                    case
                        when lower(udt_name) = 'bpchar' then 'char'
                        when lower(udt_name) = 'timestamptz' then 'timestamp with time zone'
                        when lower(udt_name) like '%int2%' then 'smallint'
                        when lower(udt_name) like '%int4%' then 'integer'
                        when lower(udt_name) like '%int8%' then 'bigint'
                        when lower(udt_name) like '%float8%' then 'double precision'
                        when lower(udt_name) like '%float4%' then 'real'
                        else udt_name
                    end ||
                    case
                        when character_maximum_length is not null then '(' || character_maximum_length || ')'
                        when lower(udt_name) = 'numeric' and numeric_precision is not null then '(' || numeric_precision || ',' || numeric_scale || ')'
                        else ''
                    end ||
                    case
                        when left(udt_name,1) = '_' then '[]'
                        else ''
                    end as column_type,
                    ordinal_position
                from information_schema.columns
                {where}
                order by table_schema, table_name, ordinal_position
            """.format(where = where)

            print query
            try:
                self.cur.execute(query)
            except:
                print "Can't select"

            rows = self.cur.fetchall()

            self.resultDataset = rows

            event.Skip()


#---------------------------------------------------------------------------
# Main function

def main(argv):
    app = ETLCodeGenApp()
    app.MainLoop()

if __name__ == "__main__":
    main(sys.argv)

