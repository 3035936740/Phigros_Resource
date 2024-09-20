import json
import struct
import sys
from UnityPy import Environment
import zipfile

SONG_BASE_SCHEMA = {
    "songId": str, 
    "songKey": str, 
    "songName": str, 
    "songTitle": str, 
    "difficulty": [float],

    "illustrator": str, 
    "charter": [str], 
    "composer": str, 

    "levels": [str], 

    "previewTimeFrom": float, 
    "previewTimeTo": float,

    "unlockList": {
        "unlockType": int, 
        "unlockInfo": [str]
    }, 
    "judgeLineImages": [[str]], # may need to refactor
    "levelMods": {
        "n": [str]
    },
    #"isCnLimited": int,

    #"hasDifferentMusic": int,
    "hasDifferentMusic+isCnLimited": int,
    "differentMusic": int,

    "previewClipDifficulty": int,

    "hasDifferentCover": int,
    "differentCover": int
}

class ByteReader:
    def __init__(self, data: bytes):
        self.data = data
        # self.debug = False
        self.position = 0
        self.d = {int: self.readInt, float: self.readFloat, str: self.readString}

    # 4字节读取数据(int)
    def readInt(self):
        self.position += 4
        return self.data[self.position - 4] ^ self.data[self.position - 3] << 8

    # 4字节读取数据(float)
    def readFloat(self):
        self.position += 4
        return struct.unpack("f", self.data[self.position - 4:self.position])[0]

    # 读取字符串
    def readString(self):
        length = self.readInt() # 读取第一个字节获取当前字符串长度
        result = self.data[self.position:self.position + length].decode()
        self.position += length // 4 * 4
        if length % 4 != 0:
            self.position += 4
        return result

    def skipString(self): # 略过字符串
        length = self.readInt()
        self.position += length // 4 * 4
        if length % 4 != 0:
            self.position += 4

    def readList(self, value: list):
        l = []
        for i in range(self.readInt()):
            t = value[0]
            if (type(t) == dict):
                t = self.readSchema(t)
                l.append(t)
            elif (type(t) == list):
                t = self.readList(t)
                l.append(t)
            elif (t == str):
                l.append(self.readString())
            else:
                l.append(self.d[t]())
        return l

    def readSchema(self, schema: dict): # 通过SONG_BASE_SCHEMA中的字典来获取数据类型
        result = []
        for x in range(self.readInt()):
            item = {}
            for key, value in schema.items():
                #print("type %s reading at %i" % (value, self.position))
                # ^ debbugging purpose
                if value in (int, float):
                    item[key] = self.d[value]()
                elif value == str:
                    item[key] = self.readString()
                elif type(value) == list:
                    l = self.readList(value)
                    item[key] = l
                elif type(value) == tuple:
                    for t in value:
                        self.d[t]()
                elif type(value) == dict:
                    item[key] = self.readSchema(value)
                else:
                    raise Exception("无")
            result.append(item)
        return result

def run(path):
    env = Environment()
    with zipfile.ZipFile(path) as apk:
        with apk.open("assets/bin/Data/globalgamemanagers.assets") as f:
            env.load_file(f.read(), name="assets/bin/Data/globalgamemanagers.assets")
        with apk.open("assets/bin/Data/level0") as f:
            env.load_file(f.read())
    for obj in env.objects:
        if obj.type.name != "MonoBehaviour":
            continue
        data = obj.read()
        if data.m_Script.get_obj().read().name == "GameInformation":
            information = data.raw_data.tobytes()
        elif data.m_Script.get_obj().read().name == "GetCollectionControl":
            collection = data.raw_data.tobytes()
        elif data.m_Script.get_obj().read().name == "TipsProvider":
            tips = data.raw_data.tobytes()

    reader = ByteReader(information)
    
    # debug
    # with open("temp/binary_file.bin", 'wb') as file:
    #     file.write(reader.data)
        
    reader.position = information.index(b"\x16\x00\x00\x00Glaciaxion.SunsetRay.0\x00\x00\n") - 4
    difficulty = []
    table = []
    musicInfos = []
    for i in range(3):
        for item in reader.readSchema(SONG_BASE_SCHEMA):
            item["songId"] = item["songId"][:-2]
            if len(item["levels"]) == 5:
                item["difficulty"].pop()
                item["charter"].pop()
            if item["difficulty"][-1] == 0:
                item["difficulty"].pop()
                item["charter"].pop()
            for i in range(len(item["difficulty"])):
                item["difficulty"][i] = round(item["difficulty"][i], 1)
            difficulty.append([item["songId"]] + item["difficulty"])
            table.append((item["songId"], item["songName"], item["composer"], item["illustrator"], *item["charter"]))
            
            sid, levels, ratings, charters = item["songId"], item["levels"], item["difficulty"], item["charter"]

            modifyItem = {
                "sid": sid, "title": item["songName"],
                "illustrator": item["illustrator"], "composer": item["composer"],
                "previewTimeFrom": item["previewTimeFrom"], "previewTimeTo": item["previewTimeTo"],
                "chartDetail": {
                    "levelList": []
                }
            }
            for index in range(len(ratings)):
                level, rating, charter = levels[index], ratings[index], charters[index]
                modifyItem["chartDetail"][level] = {
                    "rating": rating,
                    "charter": charter
                }
                modifyItem["chartDetail"]["levelList"].append(level)
            
            print(sid)
            musicInfos.append(modifyItem)
    reader.readSchema(SONG_BASE_SCHEMA)
    print("-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-")

    with open("music-info.json", "w", encoding="utf8") as f:
        f.write(json.dumps(musicInfos, ensure_ascii=False, indent=2))
    print("music-info write completed")

    with open("difficulty.tsv", "w", encoding="utf8") as f:
        for item in difficulty:
            f.write("\t".join(map(str, item)))
            f.write("\n")
    print("difficulty write completed")

    with open("info.tsv", "w", encoding="utf8") as f:
        for item in table:
            f.write("\t".join(item))
            f.write("\n")
    print("info write completed")
    
    key_schema = {"key": str, "a": int, "type": int, "b": int}
    single = []
    illustration = []
    for item in reader.readSchema(key_schema):
        if item["type"] == 0:
            single.append(item["key"])
        elif item["type"] == 2 and item["key"] != "Introduction" and item["key"] not in single:
            illustration.append(item["key"])

    with open("single.txt", "w", encoding="utf8") as f:
        for item in single:
            f.write("%s\n" % item)
    print("single write completed")
    with open("illustration.txt", "w", encoding="utf8") as f:
        for item in illustration:
            f.write("%s\n" % item)
    print("illustration write completed")

    reader = ByteReader(collection)
    collection_schema = {1: (int, int, int, str, str, str), "key": str, "index": int, 2: (int,), "title": str,
                         3: (str, str, str, str)}
    D = {}
    for item in reader.readSchema(collection_schema):
        if item["key"] in D:
            D[item["key"]][1] = item["index"]
        else:
            D[item["key"]] = [item["title"], item["index"]]
    with open("collection.tsv", "w", encoding="utf8") as f:
        for key, value in D.items():
            f.write("%s\t%s\t%s\n" % (key, value[0], value[1]))
    print("collection write completed")

    avatar_schema = {1: (int, int, int, str, str, str), "id": str, "file": str}
    table = reader.readSchema(avatar_schema)
    with open("avatar.txt", "w", encoding="utf8") as f:
        for item in table:
            f.write(item["id"])
            f.write("\n")
    print("avatar write completed")
    with open("tmp.tsv", "w", encoding="utf8") as f:
        for item in table:
            f.write("%s\t%s\n" % (item["id"], item["file"][7:]))
    print("tmp write completed")

    reader = ByteReader(tips[8:])
    with open("tips.txt", "w", encoding="utf8") as f:
        for i in range(reader.readInt()):
            f.write(reader.readString())
            f.write("\n")
    print("tips write completed")

    print("done.")

if __name__ == "__main__":
    run(sys.argv[1])
