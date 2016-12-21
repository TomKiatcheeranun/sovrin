import json

from ledger.util import F
from plenum.common.txn import TARGET_NYM, TXN_TYPE, DATA, NAME, VERSION, TYPE, ORIGIN
from plenum.test.eventually import eventually

from anoncreds.protocol.repo.public_repo import PublicRepo
from anoncreds.protocol.types import ClaimDefinition, ID, PublicKey, RevocationPublicKey, AccumulatorPublicKey, \
    Accumulator, TailsType, TimestampType
from sovrin.common.txn import GET_CRED_DEF, CRED_DEF, ATTR_NAMES, GET_ISSUER_KEY, REF, ISSUER_KEY
from sovrin.common.types import Request


def _ensureReqCompleted(reqKey, client, clbk):
    reply, err = client.replyIfConsensus(*reqKey)
    if reply is None:
        raise ValueError('not completed')
    return clbk(reply, err)


def _getData(result, error):
    data = json.loads(result.get(DATA).replace("\'", '"'))
    seqNo = None if not data else data.get(F.seqNo.name)
    return data, seqNo


def _submitData(result, error):
    data = json.loads(result.get(DATA).replace("\'", '"'))
    seqNo = result.get(F.seqNo.name)
    return data, seqNo


class SovrinPublicRepo(PublicRepo):
    def __init__(self, client, wallet):
        self.client = client
        self.wallet = wallet
        self.displayer = print

    async def getClaimDef(self, id: ID) -> ClaimDefinition:
        op = {
            TARGET_NYM: id.claimDefKey.issuerId,
            TXN_TYPE: GET_CRED_DEF,
            DATA: {
                NAME: id.claimDefKey.name,
                VERSION: id.claimDefKey.version,
            }
        }
        data, seqNo = await self._sendGetReq(op)
        return ClaimDefinition(name=data[NAME],
                               version=data[VERSION],
                               type=data[TYPE],
                               attrNames=data[ATTR_NAMES].split(","),
                               issuerId=data[ORIGIN],
                               id=seqNo)

    async def getPublicKey(self, id: ID) -> PublicKey:
        op = {
            TXN_TYPE: GET_ISSUER_KEY,
            REF: id.claimDefId,
            ORIGIN: id.claimDefKey.issuerId
        }
        data, seqNo = await self._sendGetReq(op)
        data = data[DATA]
        return PublicKey.fromStrDict(data)

    async def getPublicKeyRevocation(self, id: ID) -> RevocationPublicKey:
        pass

    async def getPublicKeyAccumulator(self, id: ID) -> AccumulatorPublicKey:
        pass

    async def getAccumulator(self, id: ID) -> Accumulator:
        pass

    async def getTails(self, id: ID) -> TailsType:
        pass

    # SUBMIT

    async def submitClaimDef(self, claimDef: ClaimDefinition):
        op = {
            TXN_TYPE: CRED_DEF,
            DATA: {
                NAME: claimDef.name,
                VERSION: claimDef.version,
                TYPE: claimDef.type,
                ATTR_NAMES: ",".join(claimDef.attrNames)
            }
        }

        data, seqNo = await self._sendSubmitReq(op)
        claimDef = ClaimDefinition(name=claimDef.name, version=claimDef.version, attrNames=claimDef.attrNames,
                                   type=claimDef.type, issuerId=self.wallet.defaultId, id=seqNo)
        return claimDef

    async def submitPublicKeys(self, id: ID, pk: PublicKey, pkR: RevocationPublicKey = None):
        data = pk.toStrDict()
        op = {
            TXN_TYPE: ISSUER_KEY,
            REF: id.claimDefId,
            DATA: data
        }

        await self._sendSubmitReq(op)

    async def submitAccumulator(self, id: ID, accumPK: AccumulatorPublicKey, accum: Accumulator, tails: TailsType):
        pass

    async def submitAccumUpdate(self, id: ID, accum: Accumulator, timestampMs: TimestampType):
        pass

    async def _sendSubmitReq(self, op):
        return await self._sendReq(op, _submitData)

    async def _sendGetReq(self, op):
        return await self._sendReq(op, _getData)

    async def _sendReq(self, op, clbk):
        req = Request(identifier=self.wallet.defaultId, operation=op)
        req = self.wallet.prepReq(req)
        self.client.submitReqs(req)

        return await eventually(_ensureReqCompleted,
                                req.key, self.client, clbk,
                                timeout=20, retryWait=0.5)
