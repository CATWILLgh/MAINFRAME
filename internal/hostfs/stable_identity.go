package hostfs

type stableFileIdentity struct {
	device           uint64
	inode            uint64
	birthSeconds     int64
	birthNanoseconds int64
}
