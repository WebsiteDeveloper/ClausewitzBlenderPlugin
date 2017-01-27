class TreeNode:
    idCounter = 1

    def __init__(self, name):
        self.name = name
        self.subNodes = []
        self.value = []
        self.id = TreeNode.idCounter
        TreeNode.idCounter += 1

    def append(self, node):
        self.subNodes.append(node)

    def print(self, indent):
        line = ""

        for i in range(0, indent):
            line += "-"

        line += self.name
        print(line)

        for i in range(0, len(self.subNodes)):
            self.subNodes[i].print(indent + 1)

    def search(self, name: str, useSelf: bool):
        if self.name == name and useSelf:
            return self
        else:
            if len(self.subNodes) > 0:
                for node in self.subNodes:
                    result = node.search(name, True)

                    if result != 0:
                        return result
            else:
                return 0

        return 0

    def searchById(self, id: int):
        if self.id == id:
            return self
        else:
            if len(self.subNodes) > 0:
                for node in self.subNodes:
                    result = node.searchById(id, True)

                    if result != 0:
                        return result
            else:
                return 0

        return 0

    def searchForParentNode(self, childNodeId: int):
        for i in range(0, len(self.subNodes)):
            if self.subNodes[i].id == childNodeId:
                return self

            newParentNode = self.subNodes[i].searchForParentNode(childNodeId)

            if newParentNode != -1:
                return newParentNode


        return -1

    def hasSubNode(self, name: str):
        for i in range(0, len(self.subNodes)):
            if self.subNodes[i].name == name:
                return True

        return False

    def Flatten(self):
        result = []

        newNode = TreeNode(self.name)
        newNode.append(self.subNodes[0])
        newNode.append(self.subNodes[1])
        result.append(newNode)

        if len(self.subNodes) > 2:
            result.extend(self.subNodes[2].Flatten())

        return result

class Tree:
    def __init__(self, rootNode: TreeNode):
        self.rootNode = rootNode

    def print(self):
        self.rootNode.print(0)

    def search(self, name):
        return self.rootNode.search(name, True)