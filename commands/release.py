from twisted.internet.utils import getProcessOutputAndValue
import binascii, fnmatch, os, re

config = {
    "access": "admin",
    "help": ".release [show name] (--previous) (--comment=TEXT) || .release Accel World || Releases the show by uploading to DCC bots, the seedbox, Nyaa, TT, and creating the blog post. Requires a .mkv and .xdelta. Use --previous for releasing a v2.",
}

def command(guid, manager, irc, channel, user, show, previous = False, comment = None):
    show = manager.master.modules["showtimes"].resolve(show)
    if not show.folder.ftp:
        raise manager.exception(u"No FTP folder given for {}".format(show.name.english))
    if not show.folder.xdcc:
        raise manager.exception(u"No XDCC folder given for {}".format(show.name.english))

    offset = 0 if previous else 1
    episode = show.episode.current + offset

    # Step 1: Search FTP for complete episode, or premux + xdelta
    folder = "/{}/{:02d}/".format(show.folder.ftp, episode)
    xdelta = yield manager.master.modules["ftp"].getLatest(folder, "*.xdelta")
    premux = yield manager.master.modules["ftp"].getLatest(folder, "*.mkv")

    if xdelta and premux:
        # Step 1b: Download premux + xdelta, merge into completed file
        irc.notice(user, u"Found xdelta and premux: {} and {}".format(xdelta, premux))

        yield manager.master.modules["ftp"].getFromCache(folder, premux, guid)
        yield manager.master.modules["ftp"].get(folder, xdelta, guid)

        out, err, code = yield getProcessOutputAndValue(manager.master.modules["utils"].getPath("xdelta3"), args=["-f","-d", os.path.join(guid, xdelta)], env=os.environ)
        if code != 0:
            manager.log(out)
            manager.log(err)
            raise manager.exception(u"Aborted releasing {}: Couldn't merge premux and xdelta.".format(show.name.english))
        irc.notice(user, u"Merged premux and xdelta")

        complete = fnmatch.filter(os.listdir(guid), "[[]Commie[]]*.mkv")
        if not complete:
            raise manager.exception(u"No completed file found after merging")
        complete = complete[0]
    else:
        raise manager.exception(u"Aborted releasing {}: Couldn't find premux and xdelta.".format(show.name.english))

    # Step 1c: Verify CRC
    try:
        with open(os.path.join(guid, complete), "rb") as f:
            crc = binascii.crc32(f.read()) & 0xFFFFFFFF
    except:
        raise manager.exception(u"Aborted releasing {}: Couldn't open completed file for CRC verification.".format(show.name.english))

    normal = u"{:08X}".format(crc)
    roman = manager.master.modules["utils"].intToRoman(crc)
    detected = re.findall("\[([^]]+)\]", complete)[1].decode("utf8")

    if detected != normal and detected != roman:
        raise manager.exception(u"Aborted releasing {}: CRC failed verification. Filename = '{}', Calculated = '{}'.".format(show.name.english, detected, normal))

    # Step 1d: Determine version number
    match = re.search("(v\d+)", complete)
    version = match.group(1) if match is not None else ""

    # Step 2: Create torrent
    irc.notice(user, u"Creating torrent")
    try:
        torrent = manager.master.modules["torrent"].makeTorrent(guid, complete)
    except:
        manager.err("Making a torrent for {}", show.name.english)
        raise manager.exception(u"Aborted releasing {}: Couldn't create torrent.".format(show.name.english))
    irc.notice(user, u"Created torrent")

    # Step 3: Upload episode to XDCC server
    irc.notice(user, u"Uploading to XDCC")
    yield manager.master.modules["ftp"].putXDCC(guid, complete, show.folder.xdcc)
    irc.notice(user, u"Uploaded to XDCC")

    # Step 4: Upload episode to seedbox
    irc.notice(user, u"Uploading to seedbox")
    yield manager.master.modules["ftp"].putSeedbox(guid, complete)
    irc.notice(user, u"Uploaded to seedbox")

    # Step 5: Start seeding torrent
    yield manager.master.modules["ftp"].putTorrent(guid, torrent)
    irc.notice(user, u"Seeding started")

    # Step 6: Upload torrent to Nyaa
    # Step 7: Get torrent link from Nyaa
    info_link, download_link = yield manager.master.modules["nyaa"].upload(guid, torrent)
    irc.notice(user, u"Uploaded to Nyaa")

    # Step 8: Upload torrent link to TT
    try:
        yield manager.master.modules["tt"].upload(download_link)
    except:
        irc.msg(channel, u"Couldn't upload to TT. Continuing to release {} regardless.".format(show.name.english))
    else:
        irc.notice(user, u"Uploaded to TT")

    # Step 9: Create blog post
    try:
        yield manager.master.modules["blog"].createPost(show, episode, version, info_link, comment)
    except:
        irc.msg(channel, u"Couldn't create blog post. Continuing to release {} regardless.".format(show.name.english))
    else:
        irce.notice(user, u"Created blog post")

    # Step 10: Mark show finished on showtimes
    try:
        yield manager.master.modules["showtimes"].finished(show)
    except:
        irc.msg(channel, u"Failed to mark show as done on showtimes")
    irc.msg(channel, u"{} released. Torrent @ {}".format(show.name.english, info_link))

    # Step 11: Update the topic
    yield manager.master.modules["showtimes"].updateTopic()

    # Step 12: Clean up
    manager.master.modules["ftp"].uncache(premux)
