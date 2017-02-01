
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
        wx.Frame.__init__(self, parent, -1, "ETL CodeGen Metadata Editor 0.2", size=(1152,700))
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

        item = fileMenu.Append(wx.ID_ANY, "&Refresh", "Refresh tree")
        self.Bind(wx.EVT_MENU, self.OnMenuRefresh, item)

        fileMenu.AppendSeparator()

        item = fileMenu.Append(wx.ID_ANY, "&Generate SQL code", "Generate SQL code")
        self.Bind(wx.EVT_MENU, self.OnMenuGenerateSQL, item)

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
                stageTableDataset = self.GetDataset('select * from {0} {1}'.format(table, where.format(parent_id)))

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
                    if stageTableItem[7] != None and stageTableItem[7] != '':
                        targetTableName = stageTableItem[6] + '_' + stageTableItem[7]
                    else:
                        targetTableName = stageTableItem[6]
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

            if (table == 'stage_table') or (table == 'stage_column'):
                self.buttonImport.SetLabel('Import ' + table.title().replace('_',' '))
                self.buttonImport.Enable()
            else:
                self.buttonImport.SetLabel('Import not available')
                self.buttonImport.Disable()

            self.buttonAdd.SetLabel('Add ' + table.title().replace('_',' '))
            self.buttonDelete.SetLabel('Delete ' + table.title().replace('_',' '))

            gridDataset = self.GetDataset('select * from {0} {1}'.format(table, where))
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
            where d.stage_db_id = (select stage_db_id from stage_table where stage_table_id = {parent_id})
            order by 1'''.format(parent_id = str(self.grid.treeItemData['parent_id'])))

        if len(selectorFkEntityList) == 0 or selectorFkEntityList[0] != '':
            selectorFkEntityList.insert(0,'')

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
                    where d.stage_db_id = (select stage_db_id from stage_table where stage_table_id = {parent_id})
                        and t.target_entity_name = '{currentTargetEntity}'
                    order by 1'''.format(parent_id = str(self.grid.treeItemData['parent_id']), \
                        currentTargetEntity = currentTargetEntity))
            else:
                selectorFkSubnameList = ['']

            if len(selectorFkSubnameList) == 0 or selectorFkSubnameList[0] != '':
                selectorFkSubnameList.insert(0,'')

            # Getting FK Entity Attributes List
            if currentTargetEntity != '':
                selectorFkAttributeList = self.GetDataAsList('''
                    select
                        c.target_attribute_name
                    from stage_column c
                        join stage_table t on t.stage_table_id = c.stage_table_id
                        join stage_db d on d.stage_db_id = t.stage_db_id
                    where d.stage_db_id = (select stage_db_id from stage_table where stage_table_id = {parent_id})
                        and t.target_entity_name = '{currentTargetEntity}'
                        and t.target_entity_subname = '{currentTargetEntitySubname}'
                    order by c.target_ordinal_pos'''.format(parent_id = str(self.grid.treeItemData['parent_id']), \
                        currentTargetEntity = currentTargetEntity, currentTargetEntitySubname = currentTargetEntitySubname))
            else:
                selectorFkAttributeList = ['']

            if len(selectorFkAttributeList) == 0 or selectorFkAttributeList[0] != '':
                selectorFkAttributeList.insert(0,'')

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
                                insert into stage_column (stage_table_id, column_name, column_type, target_ordinal_pos)
                                select {0}, '{1}', '{2}', {3}
                                """.format(parent_id, resultColumnName, resultColumnType, resultColumnPos)

                            conn.execute("""
                                insert into stage_column (stage_table_id, column_name, column_type, target_ordinal_pos)
                                select {0}, '{1}', '{2}', {3}
                                """.format(parent_id, resultColumnName, resultColumnType, resultColumnPos)
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
                                    insert into stage_table (stage_db_id, schema_name, table_name, target_entity_name, target_entity_subname)
                                    values ({0}, '{1}', '{2}', '{3}', '{4}')
                                    """.format(parent_id, resultSchemaName.lower(), resultTableName.lower(), 'dim_' + resultTableName.lower(), 'main')

                                conn.execute("""
                                    insert into stage_table (stage_db_id, schema_name, table_name, target_entity_name, target_entity_subname)
                                    values ({0}, '{1}', '{2}', '{3}', '{4}')
                                    """.format(parent_id, resultSchemaName.lower(), resultTableName.lower(), 'dim_' + resultTableName.lower(), 'main')
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


    def OnMenuGenerateSQL(self, event):
        self.log.WriteText("OnMenuGenerateSQL")
        table = self.grid.treeItemData['table']
        parent_id = str(self.grid.treeItemData['parent_id'])
        if (table != 'stage_column'):
            dlg = wx.MessageDialog(self.frame, "Please select a table in a tree to generate the SQL code for it", "Error", wx.OK | wx.ICON_ERROR)
            dlg.ShowModal()
            dlg.Destroy()
            return

        if self.grid.hasUsavedChanges:
            dlg = wx.MessageDialog(self.frame, "There are unsaved changes pending.\nDo you want to save?", "Warning", wx.YES_NO | wx.CANCEL | wx.YES_DEFAULT | wx.ICON_EXCLAMATION)
            result = dlg.ShowModal()
            dlg.Destroy()

            if result == wx.ID_YES:
                self.SaveGridChanges()

        self.GenerateSQL(parent_id)


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


    def GenerateSQL(self, stage_table_id):
        self.log.WriteText('GenerateSQL')
        #con = sqlite3.connect(":memory:")
        #con.row_factory = sqlite3.Row
        #cur = con.cursor()
        #cur.execute("select 'John' as name, 42 as age")
        #for row in cur:
        #    assert row[0] == row["name"]
        #    assert row["name"] == row["nAmE"]
        #    assert row[1] == row["age"]
        #    assert row[1] == row["AgE"]
        with sqlite3.connect(self.db_filename) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("""
select
    d.staging_schema,
    d.is_delete_temp_tables,
    t.schema_name,
    t.table_name,
    t.table_expression,
    t.target_entity_schema,
    t.target_entity_name,
    t.target_entity_subname,
    case
        when coalesce(t.target_entity_subname,'') != ''
            then t.target_entity_name || '_' || t.target_entity_subname
        else t.target_entity_name
    end as target_entity_full_name,
    c.column_name,
    c.column_expression,
    case
        when c.is_unix_timestamp = 1
            then 'decode(' || c.column_name || ', 0, NULL, timestamp ''epoch'' + ' || c.column_name || ' * interval ''1 second'') as ' || c.column_name
        else
            case when coalesce(c.column_expression, '') != '' then c.column_expression || ' as ' || c.column_name
            else c.column_name end
    end as column_value_decoded,
    case
        when (lower(c.column_type) in ('date','timestamp','datetime')) or (c.is_unix_timestamp = 1)
            then 'nvl(to_char(' || c.column_name || ',''YYYYMMDD'') || '''','''')'
        else 'nvl(' || c.column_name || ' || '''','''')'
    end as column_value_for_bk,
    case
        when lower(c.column_type) = 'date'
            then 'nvl(to_char(' || c.column_name || ',''YYYYMMDD'') || '''','''')'
        when (lower(c.column_type) in ('timestamp','datetime')) or (c.is_unix_timestamp = 1)
            then 'nvl(to_char(' || c.column_name || ',''YYYYMMDDHH24MISS'') || '''','''')'
        else 'nvl(' || c.column_name || ' || '''','''')'
    end as column_value_as_char,
    c.column_type,
    c.is_bk,
    c.target_ordinal_pos,
    c.target_attribute_name,
    case
        when (c.is_unix_timestamp = 1)
            then 'timestamp'
        else c.target_attribute_type
    end as target_attribute_type,
    t_fk.target_entity_schema as fk_entity_schema,
    c.fk_entity_name,
    c.is_fk_inferred,
    c.fk_entity_subname,
    case
        when coalesce(c.fk_entity_subname,'') != ''
            then c.fk_entity_name || '_' || c.fk_entity_subname
        else c.fk_entity_name
    end as fk_entity_full_name,
    c.fk_entity_attribute,
    c.is_fk_mandatory,
    c.is_unix_timestamp,
    c.is_date_updated,
    c.target_distkey_pos,
    c.target_sortkey_pos
from stage_column c
    join stage_table t on t.stage_table_id = c.stage_table_id
    join stage_db d on d.stage_db_id = t.stage_db_id
    left join ( -- Until we have real target entities metadata, getting info from sources, avoiding inconsistencies
        select
            target_entity_name,
            max(target_entity_schema) as target_entity_schema
        from stage_table
        group by
            target_entity_name
    ) t_fk on t_fk.target_entity_name = c.fk_entity_name
where c.is_ignored != 1
    and c.stage_table_id = {stage_table_id}
order by c.target_ordinal_pos, stage_column_id
""".format(stage_table_id = stage_table_id))

            # Reading common values for all rows

            dataset = cur.fetchall()
            row = dataset[0]
            stagingSchema = row['staging_schema']
            isDeleteTempTables = row['is_delete_temp_tables']
            schemaName = row['schema_name']
            tableName = row['table_name']
            tableExpression = row['table_expression']
            targetEntitySchema = row['target_entity_schema']
            targetEntityName = row['target_entity_name']
            targetEntitySubName = row['target_entity_subname']
            targetEntityFullName = row['target_entity_full_name']
            dropTableSection = ""

            # -----------------------------------------------------------------
            # Starting code generation

            fullScriptETL = """
-- ETL code for loading {schemaName}.{tableName} to {targetEntitySchema}.{targetEntityFullName}

drop table if exists {stagingSchema}.batch;

create table {stagingSchema}.batch as
select
    getdate() as batch_date,
    0 as batch_number
;
""".format(stagingSchema = stagingSchema, schemaName = schemaName, tableName = tableName, \
        targetEntitySchema = targetEntitySchema, targetEntityFullName = targetEntityFullName)

            dropTableSection += """
drop table if exists {stagingSchema}.batch;""".format(stagingSchema = stagingSchema)

            # -----------------------------------------------------------------
            # Generating DDL section

            DDLTableColumns = """
    entity_key bigint distkey,"""

            for row in dataset:
                if row['fk_entity_name'] != None and row['fk_entity_name'] != '':
                    DDLTableColumns += """
    {target_attribute_name}_key bigint,
    {target_attribute_name} {target_attribute_type},""".format(target_attribute_name = row['target_attribute_name'], target_attribute_type = row['target_attribute_type'])

                else:
                    DDLTableColumns += """
    {target_attribute_name} {target_attribute_type},""".format(target_attribute_name = row['target_attribute_name'], target_attribute_type = row['target_attribute_type'])

            DDLTableColumns = DDLTableColumns[:-1]

            # Putting together Stage2 table
            DDLSection = """
-- Generating DDL for all required tables, only run if the tables don't exist yet
/*
drop table if exists {targetEntitySchema}.{targetEntityName}_pk_lookup;

create table {targetEntitySchema}.{targetEntityName}_pk_lookup (
    entity_bk varchar(max) not null distkey,
    entity_key bigint not null identity
);

drop table if exists {targetEntitySchema}.{targetEntityFullName}_batch_info;

create table {targetEntitySchema}.{targetEntityFullName}_batch_info (
    entity_key bigint not null distkey,
    is_inferred smallint not null default 0,
    hash varchar(40),
    batch_date timestamp not null,
    batch_number bigint not null
);

drop table if exists {targetEntitySchema}.{targetEntityFullName};

create table {targetEntitySchema}.{targetEntityFullName} ({DDLTableColumns}
);

drop table if exists {targetEntitySchema}.{targetEntityFullName}_history;

create table {targetEntitySchema}.{targetEntityFullName}_history (
    -- History part
    is_inferred smallint default 0,
    hash varchar(40),
    batch_date timestamp,
    batch_number bigint,
    batch_date_new timestamp,
    batch_number_new bigint,
    -- Main part {DDLTableColumns}
);
*/
""".format(DDLTableColumns = DDLTableColumns, targetEntityName = targetEntityName, targetEntityFullName = targetEntityFullName, \
        targetEntitySchema = targetEntitySchema)

            fullScriptETL += DDLSection

            # -----------------------------------------------------------------
            # Generating Stage1 section with all Business Keys

            # Building a sub-query for a source table with all required columns transformations
            sourceTableColumns = ""

            # Building a list of columns to select
            sourceColumnsList = ""

            # Building the entity's Business Key expression
            sourceColumnsBK = ""

            # Building the Foreign Business Keys expressions
            sourceColumnsFKBK = ""

            # Building the source columns hash
            sourceColumnsHash = ""

            # Trying to find the Date Updated column, if any
            sourceColumnDateUpdated = ""

            for row in dataset:

                sourceTableColumns += """
        {column_value_decoded},""".format(column_value_decoded = row['column_value_decoded'])

                sourceColumnsList += """
    {column_name},""".format(column_name = row['column_name'])

                sourceColumnsHash += """
        {column_value_as_char} ||""".format(column_value_as_char = row['column_value_as_char'])

                if row['is_bk'] == 1:
                    sourceColumnsBK += "{column_value_as_char} || '^' || ".format(column_value_as_char = row['column_value_as_char'])

                if row['fk_entity_name'] != None and row['fk_entity_name'] != '':
                    sourceColumnsFKBK += """
    {column_value_for_bk} as {column_name}_{fk_entity_name}_bk,""".format(column_value_for_bk = row['column_value_for_bk'], \
                    column_name = row['column_name'], fk_entity_name = row['fk_entity_name'])

                if row['is_date_updated'] == 1:
                    sourceColumnDateUpdated = "{0} desc, ".format(row['column_name'])

            sourceTableColumns = sourceTableColumns[:-1] # Removing the last comma

            sourceColumnsBK = sourceColumnsBK[:-11] # Removing the last concatenation

            if tableExpression != None and tableExpression != '':
                sourceTableSelect = """
    select {sourceTableColumns}
    from (
{tableExpression}
    )
    """.format(sourceTableColumns = sourceTableColumns, tableExpression = tableExpression)

            else:
                sourceTableSelect = """
    select {sourceTableColumns}
    from {schemaName}.{tableName}
    """.format(sourceTableColumns = sourceTableColumns, schemaName = schemaName, tableName = tableName)

            sourceColumnsHash = sourceColumnsHash[:-3] # Removing the ||

            fullScriptETL += """
drop table if exists {stagingSchema}.{targetEntityFullName}_stage1;

create table {stagingSchema}.{targetEntityFullName}_stage1 as
select {sourceColumnsList}
    {sourceColumnsBK} as entity_bk, {sourceColumnsFKBK}
    func_sha1( {sourceColumnsHash}
    ) as hash,
    row_number() over (partition by entity_bk order by {sourceColumnDateUpdated}hash) as row_number
from ({sourceTableSelect});

""".format(stagingSchema = stagingSchema, targetEntityFullName = targetEntityFullName, sourceColumnsList = sourceColumnsList, \
    sourceColumnsBK = sourceColumnsBK, sourceColumnsFKBK = sourceColumnsFKBK, sourceColumnsHash = sourceColumnsHash, \
    sourceColumnDateUpdated = sourceColumnDateUpdated, sourceTableSelect = sourceTableSelect)

            dropTableSection += """
drop table if exists {stagingSchema}.{targetEntityFullName}_stage1;""".format(stagingSchema = stagingSchema, \
    targetEntityFullName = targetEntityFullName)

            # -----------------------------------------------------------------
            # Generating Inferred sections for each row with FK

            inferredEntitiesSection = ""

            for row in dataset:
                if row['fk_entity_attribute'] != None and row['fk_entity_attribute'] != '':
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

                if row['fk_entity_full_name'] != None and row['fk_entity_full_name'] != '' and row['is_fk_inferred'] == 1:
                    inferredEntitiesSection += """
-- Inferred entity: {fk_entity_full_name}

drop table if exists {stagingSchema}.{fk_entity_full_name}_inferred_stage;

create table {stagingSchema}.{fk_entity_full_name}_inferred_stage as
select
    p.entity_key, -- Not null if entity exists, but was not loaded to this entity suffix before
    s1.{column_name}_{fk_entity_name}_bk as entity_bk {targetAttributeSelect}
from {stagingSchema}.{targetEntityFullName}_stage1 s1
    left join {fk_entity_schema}.{fk_entity_name}_pk_lookup p
        on p.entity_bk = s1.{column_name}_{fk_entity_name}_bk
    left join {fk_entity_schema}.{fk_entity_full_name}_batch_info bi
        on bi.entity_key = p.entity_key
where s1.row_number = 1
    and bi.entity_key is null -- Entity either completely new or was not loaded to this entity suffix before
group by 1,2
;

insert into {fk_entity_schema}.{fk_entity_name}_pk_lookup (entity_bk)
select i.entity_bk
from {stagingSchema}.{fk_entity_full_name}_inferred_stage i
where i.entity_key is null -- Entity is completely new
;

analyze {fk_entity_schema}.{fk_entity_name}_pk_lookup;

insert into {fk_entity_schema}.{fk_entity_full_name}_batch_info (
    entity_key,
    is_inferred,
    hash,
    batch_date,
    batch_number
)
select
    p.entity_key, -- Using just generated or already exising key which was not loaded to this entity suffix before
    1 as is_inferred,
    '{targetEntitySchema}.{targetEntityFullName}' as hash,
    b.batch_date,
    b.batch_number
from {stagingSchema}.{fk_entity_full_name}_inferred_stage i
    left join {fk_entity_schema}.{fk_entity_name}_pk_lookup p
        on p.entity_bk = i.entity_bk
    cross join {stagingSchema}.batch b
;

analyze {fk_entity_schema}.{fk_entity_full_name}_batch_info;

insert into {fk_entity_schema}.{fk_entity_full_name} (
    entity_key {targetAttributeInsertColumn}
)
select
    p.entity_key {targetAttributeInsertSelect}
from {stagingSchema}.{fk_entity_full_name}_inferred_stage i
    join {fk_entity_schema}.{fk_entity_name}_pk_lookup p
        on p.entity_bk = i.entity_bk
;

analyze {fk_entity_schema}.{fk_entity_full_name};

""".format(stagingSchema = stagingSchema, schemaName = schemaName, tableName = tableName, column_name = row['column_name'], \
    fk_entity_schema = row['fk_entity_schema'], fk_entity_name = row['fk_entity_name'], fk_entity_full_name = row['fk_entity_full_name'], \
    targetEntitySchema = targetEntitySchema, targetEntityFullName = targetEntityFullName, targetAttributeSelect = targetAttributeSelect, \
    targetAttributeInsertColumn = targetAttributeInsertColumn, targetAttributeInsertSelect = targetAttributeInsertSelect)

                    dropTableSection += """
drop table if exists {stagingSchema}.{fk_entity_full_name}_inferred_stage;""".format(stagingSchema = stagingSchema, \
    fk_entity_full_name = row['fk_entity_full_name'])

            if inferredEntitiesSection != "":
                fullScriptETL += """
-- Inferred entities loading start
{inferredEntitiesSection}
-- Inferred entities loading end

""".format(inferredEntitiesSection = inferredEntitiesSection)

            # -----------------------------------------------------------------
            # Generating Lookup section

            lookupSection = """
-- Generating keys for new entities, populating the lookup

drop table if exists {stagingSchema}.{targetEntityFullName}_pk_batch_info_stage;

create table {stagingSchema}.{targetEntityFullName}_pk_batch_info_stage as
select
    s1.entity_bk,
    p.entity_key, -- Will be null for new entities
    bi.is_inferred as is_inferred_old,
    0 as is_inferred,
    bi.hash as hash_old, -- Saving old hash and batch information for updated entities
    s1.hash,
    bi.batch_date as batch_date_old,
    bi.batch_number as batch_number_old,
    b.batch_date,
    b.batch_number
from {stagingSchema}.{targetEntityFullName}_stage1 s1
    left join {targetEntitySchema}.{targetEntityName}_pk_lookup p
        on p.entity_bk = s1.entity_bk
    left join {targetEntitySchema}.{targetEntityFullName}_batch_info bi
        on bi.entity_key = p.entity_key
    cross join {stagingSchema}.batch b
where s1.row_number = 1
    and ((p.entity_key is null)    -- New entity
        or (bi.entity_key is null) -- Entity key exists, but not in this entity subname (sattelite)
        or (bi.is_inferred = 1)     -- This entity subname was loaded, but as inferred
        or (bi.hash != s1.hash))    -- This entity subname was loaded, but the attributes changed
;

-- Inserting new entities to PK Lookup, generating keys

insert into {targetEntitySchema}.{targetEntityName}_pk_lookup (entity_bk)
select ps.entity_bk
from {stagingSchema}.{targetEntityFullName}_pk_batch_info_stage ps
where ps.entity_key is null
;

analyze {targetEntitySchema}.{targetEntityName}_pk_lookup;

-- Inserting Batch information and Hash for new entities

insert into {targetEntitySchema}.{targetEntityFullName}_batch_info (
    entity_key,
    is_inferred,
    hash,
    batch_date,
    batch_number
)
select
    p.entity_key,
    ps.is_inferred,
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
    hash = ps.hash,
    batch_date = ps.batch_date,
    batch_number = ps.batch_number
from {stagingSchema}.{targetEntityFullName}_pk_batch_info_stage ps
where ps.entity_key = {targetEntitySchema}.{targetEntityFullName}_batch_info.entity_key
    and ps.batch_number_old is not null -- This entity subname was already loaded
;

analyze {targetEntitySchema}.{targetEntityFullName}_batch_info;
""".format(stagingSchema = stagingSchema, targetEntityName = targetEntityName, targetEntityFullName = targetEntityFullName, \
        targetEntitySchema = targetEntitySchema)

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
                if row['fk_entity_name'] != None and row['fk_entity_name'] != '':
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

create table {stagingSchema}.{targetEntityFullName}_stage2 as
select
    p.entity_key, {stage2SelectColumns}
from {stagingSchema}.{targetEntityFullName}_pk_batch_info_stage as ps    -- Only new, inferred or updated entities
    join {stagingSchema}.{targetEntityFullName}_stage1 as s1    -- Taking other columns from the source table
        on s1.entity_bk = ps.entity_bk
    join {targetEntitySchema}.{targetEntityName}_pk_lookup as p    -- Using just generated or already exising keys
        on p.entity_bk = ps.entity_bk {stage2SelectJoins}
where s1.row_number = 1
;
""".format(stagingSchema = stagingSchema, targetEntityName = targetEntityName, targetEntityFullName = targetEntityFullName, \
        targetEntitySchema = targetEntitySchema, stage2SelectColumns = stage2SelectColumns, stage2SelectJoins = stage2SelectJoins)

            dropTableSection += """
drop table if exists {stagingSchema}.{targetEntityFullName}_stage2;""".format(stagingSchema = stagingSchema, \
    targetEntityFullName = targetEntityFullName)

            fullScriptETL += stage2Section

            # -----------------------------------------------------------------
            # Generating History section

            historySection = """
-- Inserting updated entities to History and deleting them from target table

insert into {targetEntitySchema}.{targetEntityFullName}_history
select
    ps.is_inferred_old as is_inferred,
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
;

analyze {targetEntitySchema}.{targetEntityFullName}_history;

delete from {targetEntitySchema}.{targetEntityFullName}
where entity_key in ( -- or where exists
    select ps.entity_key
    from {stagingSchema}.{targetEntityFullName}_pk_batch_info_stage ps
    where ps.entity_key is not null
        and ps.batch_number_old is not null -- This entity suffix already existed
);
""".format(stagingSchema = stagingSchema, targetEntityFullName = targetEntityFullName, targetEntitySchema = targetEntitySchema)

            fullScriptETL += historySection

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
""".format(stagingSchema = stagingSchema, targetEntityFullName = targetEntityFullName, targetEntitySchema = targetEntitySchema, \
    targetTableColumns = targetTableColumns)

            fullScriptETL += insertTargetSection

            # -----------------------------------------------------------------
            # Generating a drop table statements if needed

            if isDeleteTempTables != None and isDeleteTempTables == 1:
                fullScriptETL += """
-- Dropping temporary staging tables
{dropTableSection}
""".format(dropTableSection = dropTableSection)

            # -----------------------------------------------------------------
            # Saving a file

            saveFileDialog = wx.FileDialog(self.frame, "Save SQL file", "", targetEntityFullName,
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
                        else udt_name
                    end ||
                    case
                        when character_maximum_length is not null then '(' || character_maximum_length || ')'
                        when lower(udt_name) = 'numeric' then '(' || numeric_precision || ',' || numeric_scale || ')'
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

